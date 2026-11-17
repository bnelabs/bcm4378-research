#!/usr/bin/env python3
"""Compare the file layout of local Wi-Fi firmware images."""

import argparse
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import re

from inspect_firmware import MARKERS, inspect_image_bytes, read_artifact


OPENING_BLOCK_BYTES = 32
MIN_UNIFORM_RUN_BYTES = 256
UNIFORM_RUN = re.compile(rb"(.)\1{%d,}" % (MIN_UNIFORM_RUN_BYTES - 1), re.DOTALL)
BLOCK_BYTES = 4096
MAX_BLOCKS_PER_IMAGE = 512
MIN_DISTINCT_BYTE_VALUES = 12
MAX_LISTED_RUNS = 12


def describe_image(data, identity):
    runs = [
        {
            "file_offset": match.start(),
            "bytes": match.end() - match.start(),
            "byte_hex": match.group(1).hex(),
        }
        for match in UNIFORM_RUN.finditer(data)
    ]
    opening = None
    if len(data) >= 2 * OPENING_BLOCK_BYTES:
        opening = (
            data[:OPENING_BLOCK_BYTES]
            == data[OPENING_BLOCK_BYTES : 2 * OPENING_BLOCK_BYTES]
        )
    return {
        **inspect_image_bytes(data, identity),
        "opening_32_byte_block_repeated": opening,
        "uniform_run_count": len(runs),
        "uniform_run_bytes": sum(run["bytes"] for run in runs),
        "longest_uniform_runs": sorted(
            runs, key=lambda run: (-run["bytes"], run["file_offset"])
        )[:MAX_LISTED_RUNS],
    }


def common_edge_bytes(left, right):
    matched = 0
    for left_byte, right_byte in zip(left, right):
        if left_byte != right_byte:
            break
        matched += 1
    return matched


def coalesce_blocks(matches):
    runs = []
    for source_offset, target_offset in matches:
        if runs:
            previous = runs[-1]
            if (
                source_offset == previous["source_file_offset"] + previous["bytes"]
                and target_offset == previous["target_file_offset"] + previous["bytes"]
            ):
                previous["bytes"] += BLOCK_BYTES
                continue
        runs.append(
            {
                "source_file_offset": source_offset,
                "target_file_offset": target_offset,
                "bytes": BLOCK_BYTES,
            }
        )
    return sorted(runs, key=lambda run: (-run["bytes"], run["source_file_offset"]))


def extend_match(source, target, run):
    source_view = memoryview(source)
    target_view = memoryview(target)
    source_offset = run["source_file_offset"]
    target_offset = run["target_file_offset"]
    size = run["bytes"]
    before = common_edge_bytes(
        reversed(source_view[:source_offset]), reversed(target_view[:target_offset])
    )
    after = common_edge_bytes(
        source_view[source_offset + size :], target_view[target_offset + size :]
    )
    return {
        "source_file_offset": source_offset - before,
        "target_file_offset": target_offset - before,
        "bytes": before + size + after,
    }


def compare_blocks(source, target):
    block_count = len(source) // BLOCK_BYTES
    stride = max(1, (block_count + MAX_BLOCKS_PER_IMAGE - 1) // MAX_BLOCKS_PER_IMAGE)
    block_indices = range(0, block_count, stride)
    outcomes = Counter()
    shifts = Counter()
    matched_offsets = []
    for index in block_indices:
        offset = index * BLOCK_BYTES
        block = source[offset : offset + BLOCK_BYTES]
        if len(set(block)) < MIN_DISTINCT_BYTE_VALUES:
            outcomes["skipped_low_diversity"] += 1
            continue
        if source.find(block) != offset or source.find(block, offset + 1) >= 0:
            outcomes["skipped_multiple_source_offsets"] += 1
            continue
        target_offset = target.find(block)
        if target_offset < 0:
            outcomes["unmatched"] += 1
        elif target.find(block, target_offset + 1) >= 0:
            outcomes["matched_multiple_target_offsets"] += 1
        else:
            matched_offsets.append((offset, target_offset))
            shift = target_offset - offset
            if shift == 0:
                outcomes["matched_at_same_offset"] += 1
            else:
                outcomes["matched_at_shifted_offset"] += 1
                shifts[shift] += 1

    runs = coalesce_blocks(matched_offsets)
    return {
        "source_complete_blocks": block_count,
        "source_sample_stride_blocks": stride,
        "source_sampled_blocks": len(block_indices),
        "skipped_low_diversity": outcomes["skipped_low_diversity"],
        "skipped_multiple_source_offsets": outcomes["skipped_multiple_source_offsets"],
        "unmatched": outcomes["unmatched"],
        "matched_multiple_target_offsets": outcomes["matched_multiple_target_offsets"],
        "matched_at_same_offset": outcomes["matched_at_same_offset"],
        "matched_at_shifted_offset": outcomes["matched_at_shifted_offset"],
        "shifted_match_counts_by_delta_bytes": [
            {"target_minus_source_bytes": shift, "blocks": count}
            for shift, count in sorted(shifts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "longest_contiguous_matched_runs": runs[:MAX_LISTED_RUNS],
        "extended_longest_match": extend_match(source, target, runs[0]) if runs else None,
    }


def compare_pair(left, right, left_report, right_report):
    left_counts = left_report["selected_literal_counts"]
    right_counts = right_report["selected_literal_counts"]
    return {
        "left_path": left_report["file"]["path"],
        "right_path": right_report["file"]["path"],
        "overlapping_bytes": min(len(left), len(right)),
        "same_offset_equal_bytes": sum(a == b for a, b in zip(left, right)),
        "common_prefix_bytes": common_edge_bytes(left, right),
        "common_suffix_bytes": common_edge_bytes(reversed(left), reversed(right)),
        "literal_count_differences": {
            marker: {"left": left_counts[marker], "right": right_counts[marker]}
            for marker in MARKERS
            if left_counts[marker] != right_counts[marker]
        },
        "left_blocks_in_right": compare_blocks(left, right),
        "right_blocks_in_left": compare_blocks(right, left),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, nargs="+", help="At least two local firmware files")
    args = parser.parse_args()
    if len(args.images) < 2:
        parser.error("Provide at least two local firmware files")

    try:
        images = []
        for image in args.images:
            data, identity = read_artifact(image)
            images.append((data, describe_image(data, identity)))
    except (OSError, ValueError) as error:
        parser.error(str(error))

    comparisons = [
        compare_pair(left, right, left_report, right_report)
        for (left, left_report), (right, right_report) in combinations(images, 2)
    ]
    report = {
        "method": {
            "minimum_reported_uniform_run_bytes": MIN_UNIFORM_RUN_BYTES,
            "source_block_bytes": BLOCK_BYTES,
            "minimum_distinct_byte_values_per_block": MIN_DISTINCT_BYTE_VALUES,
            "maximum_source_sampled_blocks": MAX_BLOCKS_PER_IMAGE,
            "maximum_listed_runs_per_region_type": MAX_LISTED_RUNS,
            "block_search": (
                "Exact source-aligned blocks, sought at every target byte offset. "
                "A matched block contributes one mapping when each image contains it once. "
                "The longest coalesced match is extended byte by byte in both directions."
            ),
        },
        "images": [report for _, report in images],
        "comparisons": comparisons,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
