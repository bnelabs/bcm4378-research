#!/usr/bin/env python3
"""Summarize a local Wi-Fi firmware image and optional platform plist."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import plistlib
import re
from xml.parsers.expat import ExpatError


MAX_ARTIFACT_SIZE = 64 * 1024 * 1024
FIRMWARE_TAG = re.compile(
    rb"<FW-TAG>(?P<build>[!-~]+) Version=(?P<version>[0-9.]+) "
    rb"Date=(?P<build_date>[0-9TZ:+-]+) FWID=(?P<firmware_id>[0-9a-fA-F-]+)"
    rb"(?=[\x00-\x20]|$)"
)
UCODE_TAG = re.compile(
    rb"<UCODE-TAG>path=(?:[!-~]*/)?(?P<family>[A-Za-z0-9._-]+)@(?P<revision>[0-9]+) "
    rb"major=(?P<major>[0-9]+) minor=(?P<minor>[0-9]+) diff_ct=(?P<diff_count>[0-9]+) "
    rb"prebuilt=(?P<prebuilt>[01])(?=[\x00-\x20]|$)"
)
MARKERS = (
    "arp_ol",
    "awdl",
    "awdl_doiovar_patch",
    "awdl_psf_dwell",
    "btc_esco_awdl",
    "btc_wifi_prot",
    "he_twt",
    "ndoe",
    "pkt_filter",
    "roam_5g_bandboost",
    "sdb",
    "twt",
    "wnm_btm_rssi_thresh",
    "wowl_gpio",
)
MARKER_PATTERN = re.compile(
    rb"(?<![a-z0-9_])(?:"
    + b"|".join(marker.encode("ascii") for marker in MARKERS)
    + rb")(?![a-z0-9_])",
    re.IGNORECASE,
)
CONFIG_KEYS = (
    "bcom.btc.params",
    "bcom.roam.default",
    "bcom.roam.profiles",
    "bcom.wow.magic-packet",
    "wlan.awdl.params",
    "wlan.llw.tx.ring.size",
    "wlan.rx.ring.size",
    "wlan.sdb.profile",
    "wlan.tethering.enabled",
    "wlan.tx.ring.size",
    "wlan.tx.submission-queue.size",
    "wlan.wnm.enabled",
)


def read_artifact(path):
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"Expected a regular file at {path}")
    with resolved.open("rb") as file:
        data = file.read(MAX_ARTIFACT_SIZE + 1)
    if not data or len(data) > MAX_ARTIFACT_SIZE:
        raise ValueError(f"Expected a nonempty file up to 64 MiB at {path}")
    identity = {
        "path": str(path),
        "resolved_path": str(resolved),
        "bytes": len(data),
        "sha256": sha256(data).hexdigest(),
    }
    return data, identity


def inspect_image_bytes(data, identity):
    build_tags = [
        {key: value.decode("ascii") for key, value in match.groupdict().items()}
        for match in FIRMWARE_TAG.finditer(data)
    ]
    marker_counts = Counter(
        match.group().decode("ascii").lower()
        for match in MARKER_PATTERN.finditer(data)
    )
    return {
        "file": identity,
        "starts_with_hdr0": data.startswith(b"HDR0"),
        "build_tags": build_tags,
        "selected_literal_counts": {marker: marker_counts[marker] for marker in MARKERS},
    }


def inspect_embedded_metadata(data):
    ucode_tags = [
        {
            "file_offset": match.start(),
            "family": match["family"].decode("ascii"),
            "revision": int(match["revision"]),
            "major": int(match["major"]),
            "minor": int(match["minor"]),
            "diff_count": int(match["diff_count"]),
            "prebuilt": bool(int(match["prebuilt"])),
        }
        for match in UCODE_TAG.finditer(data)
    ]
    return {
        "firmware_tag_file_offsets": [match.start() for match in FIRMWARE_TAG.finditer(data)],
        "ucode_tags": ucode_tags,
    }


def profile_eight_byte_lanes(data, offset, length):
    if offset < 0 or length <= 0 or length % 8 or offset + length > len(data):
        raise ValueError("Lane window needs a nonnegative offset and a positive in-file length divisible by eight")
    lanes = [data[start:offset + length:8] for start in range(offset, offset + 8)]
    return {
        "file_offset": offset,
        "bytes": length,
        "records": length // 8,
        "zeros_by_byte_lane": [lane.count(b"\0") for lane in lanes],
        "distinct_values_by_byte_lane": [len(set(lane)) for lane in lanes],
    }


def inspect_image(path, include_embedded_metadata=False, lane_windows=()):
    data, identity = read_artifact(path)
    report = inspect_image_bytes(data, identity)
    if include_embedded_metadata:
        report["embedded_metadata"] = inspect_embedded_metadata(data)
    if lane_windows:
        report["eight_byte_lane_profiles"] = [
            profile_eight_byte_lanes(data, offset, length) for offset, length in lane_windows
        ]
    return report


def inspect_platform_config(path):
    data, identity = read_artifact(path)
    config = plistlib.loads(data)
    if not isinstance(config, dict):
        raise ValueError(f"Expected a plist dictionary at {path}")
    keys = {}
    for key in CONFIG_KEYS:
        if key in config:
            value = config[key]
            summary = {"type": type(value).__name__}
            if isinstance(value, bytes):
                summary["bytes"] = len(value)
            elif isinstance(value, (bool, int)):
                summary["value"] = value
            keys[key] = summary
    return {"file": identity, "selected_keys": keys}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Local firmware image")
    parser.add_argument("--platform-config", type=Path, help="Local platform plist")
    parser.add_argument(
        "--embedded-metadata", action="store_true", help="Include file offsets and microcode build fields"
    )
    parser.add_argument(
        "--lane-window",
        type=int,
        nargs=2,
        action="append",
        default=[],
        metavar=("OFFSET", "BYTES"),
        help="Profile byte lanes in a file window, without outputting its contents",
    )
    args = parser.parse_args()
    try:
        report = {
            "firmware": inspect_image(
                args.image, include_embedded_metadata=args.embedded_metadata, lane_windows=args.lane_window
            )
        }
        if args.platform_config:
            report["platform_config"] = inspect_platform_config(args.platform_config)
    except (OSError, ValueError, plistlib.InvalidFileException, ExpatError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
