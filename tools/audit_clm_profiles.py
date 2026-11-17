#!/usr/bin/env python3
"""Audit BCM4378 CLM metadata and file identities in local firmware roots."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from inspect_firmware import read_artifact
from inspect_radio_sidecars import BLOB_HEADER, CLM_HEADER, inspect_blob
from inventory_board_profiles import REVISIONS, resolve_local


KYUSHU_NAMES = tuple(f"C-4378__s-{revision}/kyushu.clmb" for revision in REVISIONS)


def read_profile(path):
    report = inspect_blob(path, "clm")
    data, identity = read_artifact(path)
    if identity != report["file"]:
        raise ValueError(f"CLM file changed during inspection at {path}")

    regions = [data[entry["offset"]:entry["offset"] + entry["bytes"]] for entry in report["entries"]]
    primary, _ = regions
    profile = {
        "bytes": identity["bytes"],
        "sha256": identity["sha256"],
        "header": report["header"],
        "metadata": report["clm_metadata"],
        "records": [
            {"bytes": len(region), "crc32": entry["crc32"], "sha256": sha256(region).hexdigest()}
            for region, entry in zip(regions, report["entries"])
        ],
        "dataset_header_bytes": CLM_HEADER.size,
        "dataset_header_sha256": sha256(primary[:CLM_HEADER.size]).hexdigest(),
        "dataset_body_sha256": sha256(primary[CLM_HEADER.size:]).hexdigest(),
        "records_are_contiguous_to_eof": (
            report["entries"][0]["offset"] == report["header"]["bytes"]
            and report["entries"][1]["offset"] == report["header"]["bytes"] + len(primary)
            and report["bytes_outside_header_and_entries"] == 0
        ),
    }
    return data, regions, profile


def inventory(directory, cache, profiles):
    root = directory.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Expected a firmware directory at {directory}")

    by_name = {}
    groups = {}
    counts = {}
    for revision in REVISIONS:
        chip_directory = root / f"C-4378__s-{revision}"
        if not chip_directory.is_dir():
            counts[revision] = {"status": "missing"}
            continue
        resolve_local(chip_directory, root)
        digests = set()
        paths = sorted(chip_directory.glob("*.clmb"))
        for path in paths:
            target = resolve_local(path, root)
            if target not in cache:
                cache[target] = read_profile(target)
            _, _, profile = cache[target]
            digest = profile["sha256"]
            filename = path.relative_to(root).as_posix()
            digests.add(digest)
            group = groups.setdefault(digest, {"sha256": digest, "regular_names": [], "symlink_targets": {}})
            if path.is_symlink():
                group["symlink_targets"][filename] = target.relative_to(root).as_posix()
            else:
                group["regular_names"].append(filename)
            by_name[filename] = cache[target]
            profiles[digest] = profile
        counts[revision] = {"status": "available", "names": len(paths), "distinct_payloads": len(digests)}

    if not by_name:
        raise ValueError(f"No BCM4378 CLM files at {directory}")
    return {
        "directory": str(directory),
        "steppings": counts,
        "alias_groups": list(groups.values()),
        "kyushu_cross_stepping": compare_kyushu(by_name),
    }, by_name


def compare_kyushu(by_name):
    if any(name not in by_name for name in KYUSHU_NAMES):
        return None
    left, right = (by_name[name] for name in KYUSHU_NAMES)
    left_data, (left_primary, left_tail), left_profile = left
    right_data, (right_primary, right_tail), right_profile = right
    result = {
        "names": list(KYUSHU_NAMES),
        "sha256": [left_profile["sha256"], right_profile["sha256"]],
        "metadata_equal": left_profile["metadata"] == right_profile["metadata"],
        "dataset_header_equal": left_profile["dataset_header_sha256"] == right_profile["dataset_header_sha256"],
        "trailing_record_equal": left_tail == right_tail,
    }
    if len(left_data) != len(right_data) or len(left_primary) != len(right_primary):
        return result

    # The documented packed BLOB header and first entry each carry a CRC32.
    header_crc = range(8, 12)
    first_record_crc = range(BLOB_HEADER.size + 12, BLOB_HEADER.size + 16)
    different = {offset for offset, (a, b) in enumerate(zip(left_data, right_data)) if a != b}
    header_crc_differences = len(different.intersection(header_crc))
    record_crc_differences = len(different.intersection(first_record_crc))
    dataset_differences = sum(a != b for a, b in zip(left_primary, right_primary))
    dataset_common_prefix = next(
        (offset for offset, (a, b) in enumerate(zip(left_primary, right_primary)) if a != b),
        len(left_primary),
    )
    result.update({
        "same_offset_differences": len(different),
        "header_crc_bytes_different": header_crc_differences,
        "first_record_crc_bytes_different": record_crc_differences,
        "dataset_bytes_different": dataset_differences,
        "dataset_common_prefix_bytes": dataset_common_prefix,
    })
    if left_profile["records_are_contiguous_to_eof"] and right_profile["records_are_contiguous_to_eof"]:
        result["whole_file_changes_accounted_for_by_dataset_and_its_crcs"] = (
            len(different) == header_crc_differences + record_crc_differences + dataset_differences
        )
    return result


def build_report(directories):
    cache = {}
    profiles = {}
    inventories = [inventory(directory, cache, profiles) for directory in directories]
    _, reference = inventories[0]
    comparisons = []
    for candidate, names in inventories[1:]:
        common = reference.keys() & names.keys()
        comparisons.append({
            "directory": candidate["directory"],
            "common_names": len(common),
            "common_names_with_identical_files": sum(reference[name][0] == names[name][0] for name in common),
            "reference_only_names": len(reference.keys() - names.keys()),
            "candidate_only_names": len(names.keys() - reference.keys()),
        })
    return {
        "inventories": [report for report, _ in inventories],
        "distinct_payloads": list(profiles.values()),
        "comparisons_with_first_directory": comparisons,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "firmware_directories", type=Path, nargs="+",
        help="One or more local roots containing C-4378__s-B1 or C-4378__s-B3 directories",
    )
    args = parser.parse_args()
    try:
        report = build_report(args.firmware_directories)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
