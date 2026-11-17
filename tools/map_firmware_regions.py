#!/usr/bin/env python3
"""Map exact byte reuse and uniform runs in local Wi-Fi firmware images."""

import argparse
from collections import defaultdict
from itertools import combinations
import json
from pathlib import Path

from compare_firmware import UNIFORM_RUN, extend_match
from inspect_firmware import read_artifact


ANCHOR_BYTES = 256
MIN_DISTINCT_BYTE_VALUES = 12
# brcmfmac's PCIe loader checks its optional RAM-size record here.
REFERENCE_RAM_SIZE_TAG_OFFSET = 0x6c


def merge_ranges(ranges):
    merged = []
    for start, stop in sorted(ranges):
        if merged and start <= merged[-1][1]:
            previous_start, previous_stop = merged[-1]
            merged[-1] = (previous_start, max(previous_stop, stop))
        else:
            merged.append((start, stop))
    return merged


def intersect_ranges(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        start = max(left[i][0], right[j][0])
        stop = min(left[i][1], right[j][1])
        if start < stop:
            result.append((start, stop))
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return result


def range_bytes(ranges):
    return sum(stop - start for start, stop in ranges)


def anchor_set(images):
    anchors = set()
    for data in images:
        for offset in range(0, len(data) - ANCHOR_BYTES + 1, ANCHOR_BYTES):
            block = data[offset : offset + ANCHOR_BYTES]
            if len(set(block)) >= MIN_DISTINCT_BYTE_VALUES:
                anchors.add(block)
    return anchors


def unique_offsets(data, anchors):
    offsets = {}
    for index in range(len(data) - ANCHOR_BYTES + 1):
        block = data[index : index + ANCHOR_BYTES]
        if block in anchors:
            offsets[block] = -1 if block in offsets else index
    return {block: position for block, position in offsets.items() if position >= 0}


def matching_regions(left, right, left_offsets, right_offsets):
    by_shift = defaultdict(list)
    for block, start in left_offsets.items():
        target = right_offsets.get(block)
        if target is not None:
            by_shift[target - start].append((start, start + ANCHOR_BYTES))

    regions = []
    for shift, anchored_ranges in sorted(by_shift.items()):
        extended_ranges = []
        for start, stop in merge_ranges(anchored_ranges):
            expanded = extend_match(
                left,
                right,
                {"source_file_offset": start, "target_file_offset": start + shift, "bytes": stop - start},
            )
            earliest = expanded["source_file_offset"]
            extended_ranges.append((earliest, earliest + expanded["bytes"]))
        regions.extend(
            {"left_offset": start, "right_offset": start + shift, "bytes": stop - start}
            for start, stop in merge_ranges(extended_ranges)
        )
    return sorted(regions, key=lambda region: (region["left_offset"], region["right_offset"]))


def summarize_image(data, identity, matched):
    uniform_runs = [
        {"offset": match.start(), "bytes": match.end() - match.start(), "byte_hex": match[1].hex()}
        for match in UNIFORM_RUN.finditer(data)
    ]
    uniform_ranges = [(run["offset"], run["offset"] + run["bytes"]) for run in uniform_runs]
    reused = merge_ranges(region for peer in matched.values() for region in peer)
    common = [(0, len(data))]
    for peer in matched.values():
        common = intersect_ranges(common, peer)
    accounted = merge_ranges(uniform_ranges + reused)
    return {
        "file": identity,
        "literal_magic_counts": {
            "ELF": data.count(b"\x7fELF"),
            "HDR0": data.count(b"HDR0"),
            "RAMS": data.count(b"RAMS"),
        },
        "reference_ram_size_tag_present": data.startswith(b"RAMS", REFERENCE_RAM_SIZE_TAG_OFFSET),
        "uniform_runs": uniform_runs,
        "uniform_run_bytes": range_bytes(uniform_ranges),
        "reused_bytes_by_other_image": {str(index): range_bytes(peer) for index, peer in matched.items()},
        "reused_bytes_in_any_other_image": range_bytes(reused),
        "reused_bytes_in_every_other_image": range_bytes(common),
        "bytes_outside_uniform_runs_and_detected_reuse": len(data) - range_bytes(accounted),
    }


def survey(artifacts):
    images, identities = zip(*artifacts)
    anchors = anchor_set(images)
    offsets = [unique_offsets(data, anchors) if anchors else {} for data in images]
    matched = [{} for _ in images]
    pairs = []
    for i, j in combinations(range(len(images)), 2):
        regions = matching_regions(images[i], images[j], offsets[i], offsets[j])
        matched[i][j] = merge_ranges(
            (region["left_offset"], region["left_offset"] + region["bytes"]) for region in regions
        )
        matched[j][i] = merge_ranges(
            (region["right_offset"], region["right_offset"] + region["bytes"]) for region in regions
        )
        pairs.append({"left_image": i, "right_image": j, "regions": regions})

    return {
        "method": {
            "anchor_bytes": ANCHOR_BYTES,
            "minimum_distinct_byte_values": MIN_DISTINCT_BYTE_VALUES,
            "anchor_positions": "Aligned blocks from every input. Search for each at any file offset.",
            "match": "Both files contain the anchor once. Extend matches by exact equality.",
            "coverage": "Union of detected byte ranges. A lower bound on byte reuse.",
            "offsets": "Zero-based file offsets.",
        },
        "images": [summarize_image(data, identities[i], matched[i]) for i, data in enumerate(images)],
        "pairs": pairs,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, nargs="+", help="At least two local firmware images")
    args = parser.parse_args()
    if len(args.images) < 2:
        parser.error("Provide at least two local firmware images")
    try:
        artifacts = [read_artifact(path) for path in args.images]
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(survey(artifacts), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
