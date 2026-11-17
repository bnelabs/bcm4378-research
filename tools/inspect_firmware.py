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


def inspect_image(path):
    return inspect_image_bytes(*read_artifact(path))


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
    args = parser.parse_args()
    try:
        report = {"firmware": inspect_image(args.image)}
        if args.platform_config:
            report["platform_config"] = inspect_platform_config(args.platform_config)
    except (OSError, ValueError, plistlib.InvalidFileException, ExpatError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
