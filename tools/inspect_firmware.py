#!/usr/bin/env python3
"""Summarize a local Wi-Fi firmware image and optional platform plist."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import plistlib
import re
from struct import Struct
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
# Chip RAM origin in Linux brcmfmac chip.c, used here as an offline model.
BCM4378_RAM_BASE = 0x352000
WORD_PAIR = Struct("<II")
THUMB_WORD = Struct("<HH")
MARKERS = (
    "arp_ol",
    "awdl",
    "awdl_doiovar_patch",
    "awdl_psf_dwell",
    "bcn_li_bcn",
    "bcn_li_dtim",
    "bcntrim",
    "bcntrim_status",
    "btc_esco_awdl",
    "btc_wifi_prot",
    "dtim_miss",
    "he_twt",
    "lpas",
    "nap_enable",
    "ndoe",
    "ops_cfg",
    "ops_status",
    "pkt_filter",
    "pm2_sleep_ret",
    "pwrstats",
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
TRANSPORT_CONFIG_KEYS = (
    "wlan.tx.ring.size",
    "wlan.rx.ring.size",
    "wlan.llw.tx.ring.size",
    "wlan.tx.submission-queue.size",
    "wlan.skywalk.packetpoolsize",
)
RADIO_POWER_CONFIG_KEYS = (
    "wlan.aoac-allowed",
    "wlan.dignap.enabled",
    "wlan.ebt.enabled",
    "wlan.lpas-allowed",
    "wlan.mimo_ps.enabled",
    "wlan.ocl.enabled",
    "wlan.ocl_awdl.enabled",
    "wlan.ops.enabled",
    "wlan.pm-thresholds.lpas",
    "wlan.pm-thresholds.wow",
    "wlan.psbw.enabled",
)
BTC_PARAMETER_KEY = "bcom.btc.params"
DFS_PROXY_KEY = "wlan.dfsproxy.enabled"
CONFIG_KEYS = (
    BTC_PARAMETER_KEY,
    "bcom.roam.default",
    "bcom.roam.profiles",
    "bcom.wow.magic-packet",
    "wlan.awdl.params",
    DFS_PROXY_KEY,
    "wlan.sdb.profile",
    "wlan.tethering.enabled",
    "wlan.txsdb.mode",
    "wlan.wnm.enabled",
    *RADIO_POWER_CONFIG_KEYS,
    *TRANSPORT_CONFIG_KEYS,
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


def find_bcm4378_overlay_rows(data):
    tags = list(FIRMWARE_TAG.finditer(data))
    if len(tags) != 1 or data[tags[0].start() - 1:tags[0].start()] != b"\n":
        raise ValueError("Expected one firmware tag preceded by a line feed")

    end = tags[0].start() - 1
    start = end
    rows = []
    while start >= WORD_PAIR.size:
        row_offset = start - WORD_PAIR.size
        first, second = WORD_PAIR.unpack_from(data, row_offset)
        slot_offset = second - BCM4378_RAM_BASE
        if first % WORD_PAIR.size or first >= BCM4378_RAM_BASE:
            break
        if slot_offset < 0 or slot_offset % WORD_PAIR.size or slot_offset + WORD_PAIR.size > row_offset:
            break
        if rows:
            next_first, next_second = rows[-1]
            if first >= next_first or second + WORD_PAIR.size != next_second:
                break
        rows.append((first, second))
        start = row_offset

    if len(rows) < 2 or rows[0][1] - BCM4378_RAM_BASE + WORD_PAIR.size > start:
        raise ValueError("No matching BCM4378 overlay table before the firmware tag")
    return start, list(reversed(rows))


def thumb_wide_branch_offset(first, second):
    # Thumb B T4 encoding. The offset is relative to the instruction address plus four.
    if (first & 0xF800) != 0xF000 or (second & 0xD000) != 0x9000:
        return None
    sign = (first >> 10) & 1
    i1 = 1 ^ sign ^ ((second >> 13) & 1)
    i2 = 1 ^ sign ^ ((second >> 11) & 1)
    offset = (sign << 24) | (i1 << 23) | (i2 << 22) | ((first & 0x3FF) << 12) | ((second & 0x7FF) << 1)
    return offset - (sign << 25)


def profile_bcm4378_overlays(data):
    table_offset, rows = find_bcm4378_overlay_rows(data)
    length = len(rows) * WORD_PAIR.size
    table_end = table_offset + length
    slots_start = rows[0][1] - BCM4378_RAM_BASE
    slots_end = slots_start + length
    later_start = BCM4378_RAM_BASE + slots_end
    later_end = BCM4378_RAM_BASE + table_offset
    branch_counts = Counter()
    later_image_hits = Counter()

    for first, second in rows:
        slot = second - BCM4378_RAM_BASE
        origins_with_hits = set()
        for word_offset in (0, THUMB_WORD.size):
            offset = thumb_wide_branch_offset(*THUMB_WORD.unpack_from(data, slot + word_offset))
            if offset is None:
                continue
            branch_counts[word_offset] += 1
            for origin, address in (("first_word", first), ("second_word", second)):
                target = address + word_offset + 4 + offset
                if later_start <= target < later_end:
                    origins_with_hits.add(origin)
        later_image_hits.update(origins_with_hits)

    return {
        "ram_base_model": BCM4378_RAM_BASE,
        "table": {
            "file_offset": table_offset,
            "record_bytes": WORD_PAIR.size,
            "records": len(rows),
            "sha256": sha256(data[table_offset:table_end]).hexdigest(),
        },
        "referenced_slots": {
            "file_offset": slots_start,
            "bytes": length,
            "sha256": sha256(data[slots_start:slots_end]).hexdigest(),
        },
        "wide_branch_words": {
            "at_slot_start": branch_counts[0],
            "at_slot_plus_four": branch_counts[THUMB_WORD.size],
        },
        "rows_with_branch_into_bytes_between_slots_and_table": {
            "first_word_pc": later_image_hits["first_word"],
            "second_word_pc": later_image_hits["second_word"],
        },
    }


def inspect_image(path, include_embedded_metadata=False, lane_windows=(), include_bcm4378_overlays=False):
    data, identity = read_artifact(path)
    report = inspect_image_bytes(data, identity)
    if include_embedded_metadata:
        report["embedded_metadata"] = inspect_embedded_metadata(data)
    if lane_windows:
        report["eight_byte_lane_profiles"] = [
            profile_eight_byte_lanes(data, offset, length) for offset, length in lane_windows
        ]
    if include_bcm4378_overlays:
        report["bcm4378_overlay_candidate"] = profile_bcm4378_overlays(data)
    return report


def decode_btc_parameters(data):
    """Decode the complete little-endian ID/value pairs consumed by macOS."""
    trailing_bytes = len(data) % WORD_PAIR.size
    pairs = memoryview(data)[: len(data) - trailing_bytes]
    return {
        "bytes": len(data),
        "parameters": [
            {"id": parameter, "value": value} for parameter, value in WORD_PAIR.iter_unpack(pairs)
        ],
        "trailing_bytes": trailing_bytes,
    }


def summarize_config_keys(config, selected_keys):
    keys = {}
    for key in selected_keys:
        if key in config:
            value = config[key]
            summary = {"type": type(value).__name__}
            if key == BTC_PARAMETER_KEY and isinstance(value, bytes):
                summary.update(decode_btc_parameters(value))
            elif isinstance(value, bytes):
                summary["bytes"] = len(value)
            elif isinstance(value, (bool, int)):
                summary["value"] = value
            keys[key] = summary
    return keys


def inspect_platform_config(path):
    data, identity = read_artifact(path)
    config = plistlib.loads(data)
    if not isinstance(config, dict):
        raise ValueError(f"Expected a plist dictionary at {path}")
    return {"file": identity, "selected_keys": summarize_config_keys(config, CONFIG_KEYS)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Local firmware image")
    parser.add_argument("--platform-config", type=Path, help="Local platform plist")
    parser.add_argument(
        "--embedded-metadata", action="store_true", help="Include file offsets and microcode build fields"
    )
    parser.add_argument(
        "--bcm4378-overlays", action="store_true", help="Profile the stock BCM4378 candidate ROM overlay table"
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
                args.image,
                include_embedded_metadata=args.embedded_metadata,
                lane_windows=args.lane_window,
                include_bcm4378_overlays=args.bcm4378_overlays,
            )
        }
        if args.platform_config:
            report["platform_config"] = inspect_platform_config(args.platform_config)
    except (OSError, ValueError, plistlib.InvalidFileException, ExpatError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
