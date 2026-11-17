#!/usr/bin/env python3
"""Inventory installed BCM4378 Bluetooth firmware and PTB file identities."""

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
from struct import unpack_from

from inspect_firmware import read_artifact


CATALOG_NAME = re.compile(
    r"BCM4378(?P<stepping>[A-Z][0-9]+)_(?P<release>[A-Za-z0-9._-]+)_PCIE_"
    r"(?:macOS_)?(?P<board>[A-Za-z0-9-]+)_OS_(?P<vendor>[A-Z]+)"
    r"_(?P<qualifiers>[A-Za-z0-9_-]+)\.(?P<extension>bin|ptb)"
)
EMBEDDED_IDENTITY = re.compile(
    rb"BCM4378(?P<stepping>[A-Z][0-9]+) Olympic PCIe macOS_"
    rb"(?P<board>[A-Za-z0-9-]+)_OS (?P<vendor>[A-Z]+)"
    rb"(?: (?P<profile>3ANT))? \[Version: (?P<version>[0-9]+(?:\.[0-9]+){3})\]"
)
HEADER_BYTES = 256
SECTION_LENGTH_OFFSETS = (20, 44, 68)
CONFIG_SECOND_MARKER_OFFSET = 66
CONFIG_IDENTITY_OFFSET = 92


def normalize_version(version):
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", version):
        raise ValueError("Expected a four-component controller version")
    return ".".join(str(int(component)) for component in version.split("."))


def inspect_image_layout(data):
    if len(data) < HEADER_BYTES:
        return None
    lengths = [unpack_from("<I", data, offset)[0] for offset in SECTION_LENGTH_OFFSETS]
    if not all(lengths) or HEADER_BYTES + sum(lengths) != len(data):
        return None

    first_length, second_length, _ = lengths
    config_offset = HEADER_BYTES + first_length + second_length
    if not data.startswith(b"BRCMcfgS", config_offset):
        return None
    config_marker = config_offset + CONFIG_SECOND_MARKER_OFFSET
    if not data.startswith(b"BRCMcfgD", config_marker):
        return None

    regions = []
    offset = HEADER_BYTES
    for length in lengths:
        region = memoryview(data)[offset:offset + length]
        regions.append({"offset": offset, "bytes": length, "sha256": sha256(region).hexdigest()})
        offset += length

    config_label_offset = config_offset + CONFIG_IDENTITY_OFFSET
    match = EMBEDDED_IDENTITY.match(data, config_label_offset, min(config_offset + 256, len(data)))
    identity = None
    if match:
        identity = {key: value.decode("ascii") for key, value in match.groupdict().items() if value}
        identity["version"] = normalize_version(identity["version"])
        identity["offset"] = config_label_offset

    return {
        "header_bytes": HEADER_BYTES,
        "regions": regions,
        "configuration_markers": {"BRCMcfgS": config_offset, "BRCMcfgD": config_marker},
        "embedded_identity": identity,
    }


def catalog_artifacts(directory):
    files = []
    unrecognized = []
    for path in sorted(directory.glob("BCM4378*")):
        if path.suffix not in (".bin", ".ptb") or not path.is_file():
            continue
        match = CATALOG_NAME.fullmatch(path.name)
        if not match:
            unrecognized.append(path.name)
            continue
        data, identity = read_artifact(path)
        row = {**match.groupdict(), "file": identity}
        if row["extension"] == "bin":
            row["container_layout"] = inspect_image_layout(data)
        files.append(row)
    return files, unrecognized


def build_report(directory, controller_version):
    files, unrecognized = catalog_artifacts(directory)
    counts = {}
    for extension in ("bin", "ptb"):
        identities = [row["file"]["sha256"] for row in files if row["extension"] == extension]
        counts[extension] = {"filenames": len(identities), "distinct_payloads": len(set(identities))}
    sections = defaultdict(list)
    for row in files:
        layout = row.get("container_layout")
        if layout:
            signature = tuple(region["sha256"] for region in layout["regions"][:2])
            sections[signature].append(Path(row["file"]["path"]).name)
    report = {
        "directory": str(directory),
        "counts": counts,
        "files": files,
        "unrecognized_filenames": unrecognized,
        "groups_with_identical_first_two_regions": list(sections.values()),
    }
    if controller_version is not None:
        version = normalize_version(controller_version)
        matches = [
            row for row in files
            if row["extension"] == "bin" and row["release"] == version
        ]
        report["controller_version_candidates"] = {
            "version": version,
            "images": [Path(row["file"]["path"]).name for row in matches],
            "ptb_catalog_partners": [
                Path(row["file"]["path"]).name
                for row in files
                if row["extension"] == "ptb" and any(
                    (row["stepping"], row["board"], row["vendor"])
                    == (image["stepping"], image["board"], image["vendor"])
                    for image in matches
                )
            ],
        }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory", nargs="?", type=Path, default=Path("/usr/share/firmware/bluetooth")
    )
    parser.add_argument("--controller-version", help="Match a reported version against catalog filenames")
    args = parser.parse_args()
    try:
        directory = args.directory.resolve(strict=True)
        if not directory.is_dir():
            raise ValueError(f"Expected a directory at {directory}")
        report = build_report(directory, args.controller_version)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
