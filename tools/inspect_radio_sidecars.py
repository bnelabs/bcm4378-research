#!/usr/bin/env python3
"""Inspect local Broadcom radio sidecars and report structural metadata."""

import argparse
from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from struct import Struct
from zlib import crc32

from inspect_firmware import read_artifact


# Public container layout in OpenWrt firmware-utils src/bcmblob.c.
BLOB_HEADER = Struct("<4sIIII")
BLOB_ENTRY = Struct("<IIIII")
ENTRY_COUNT = 2
HEADER_SIZE = BLOB_HEADER.size + ENTRY_COUNT * BLOB_ENTRY.size
HEADER_CHECKSUM_START = 12

# Public fixed-field dataset header in OpenWrt firmware-utils src/bcmclm.c.
CLM_HEADER = Struct("<8sI2s20s10sII30s22s")

# Observed TXCP prefix in all seven stock BCM4378 TxCap payloads.
TXCP_PROFILE_FIELDS = Struct("<4xI64s20s")
TXCP_TIMESTAMP = re.compile(rb"([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})\x00")

CHAIN_MASK_KEYS = ("aa2g", "aa5g", "rxchain", "txchain")
NVRAM_INTEGER = re.compile(r"[+-]?(?:0[xX][0-9a-fA-F]+|[0-9]+)")
SLICE_1_PREFIX = "slice/1/"


def verify_crc(data, expected, description):
    if crc32(data) != expected:
        raise ValueError(f"{description} CRC32 mismatch")
    return f"0x{expected:08x}"


def inspect_clm_header(payload):
    if len(payload) < CLM_HEADER.size:
        raise ValueError("Truncated CLM dataset header")
    magic, _, _, api, compiler, _, _, import_version, manufacturer = CLM_HEADER.unpack_from(payload)
    if magic != b"CLM DATA":
        raise ValueError("Expected the CLM DATA dataset marker")
    fields = {
        "api": api,
        "compiler": compiler,
        "clm_import_ver": import_version,
        "manufacturer": manufacturer,
    }
    return {key: value.split(b"\0", 1)[0].decode("ascii") for key, value in fields.items()}


def inspect_txcap_profile(payload):
    if len(payload) < TXCP_PROFILE_FIELDS.size:
        return None
    word, label_field, timestamp_field = TXCP_PROFILE_FIELDS.unpack_from(payload)
    label, terminator, padding = label_field.partition(b"\0")
    if word != 4 or not terminator or any(padding):
        return None
    if not label or not all(0x20 <= byte <= 0x7E for byte in label):
        return None

    timestamp_match = TXCP_TIMESTAMP.fullmatch(timestamp_field)
    if timestamp_match is None:
        return None
    timestamp = timestamp_match.group(1).decode("ascii")
    try:
        datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    post_text = payload[TXCP_PROFILE_FIELDS.size:]
    return {
        "word_at_offset_4_le": word,
        "profile_label": label.decode("ascii"),
        "timestamp_text": timestamp,
        "post_text": {
            "offset_in_record": TXCP_PROFILE_FIELDS.size,
            "bytes": len(post_text),
            "sha256": sha256(post_text).hexdigest(),
        },
    }


def inspect_blob(path, role):
    data, identity = read_artifact(path)
    if len(data) < HEADER_SIZE:
        raise ValueError("Truncated Broadcom BLOB header")
    magic, header_size, expected_crc, _, _ = BLOB_HEADER.unpack_from(data)
    if magic != b"BLOB":
        raise ValueError("Expected the Broadcom BLOB marker")
    if header_size != HEADER_SIZE:
        raise ValueError(f"Expected a {HEADER_SIZE}-byte two-entry BLOB header")

    view = memoryview(data)
    header_crc = verify_crc(view[HEADER_CHECKSUM_START:header_size], expected_crc, "BLOB header")
    entries = []
    for index in range(ENTRY_COUNT):
        entry_position = BLOB_HEADER.size + index * BLOB_ENTRY.size
        _, offset, size, entry_crc, _ = BLOB_ENTRY.unpack_from(data, entry_position)
        if offset < header_size or size == 0 or offset + size > len(data):
            raise ValueError(f"BLOB entry {index} has an invalid offset or length")
        checksum = verify_crc(view[offset:offset + size], entry_crc, f"BLOB entry {index}")
        entries.append({"offset": offset, "bytes": size, "crc32": checksum})

    first, second = sorted(entries, key=lambda entry: entry["offset"])
    if first["offset"] + first["bytes"] > second["offset"]:
        raise ValueError("BLOB entries overlap")
    report = {
        "file": identity,
        "container": "BLOB",
        "header": {"bytes": header_size, "crc32": header_crc},
        "entries": entries,
        "bytes_outside_header_and_entries": len(data) - header_size - sum(
            entry["bytes"] for entry in entries
        ),
    }
    entry = entries[0]
    payload = view[entry["offset"]:entry["offset"] + entry["bytes"]]
    if role == "clm":
        report["payload_marker"] = "CLM DATA"
        report["clm_metadata"] = inspect_clm_header(payload)
    else:
        if payload[:4] != b"TXCP":
            raise ValueError("Expected the TXCP dataset marker")
        report["payload_marker"] = "TXCP"
        profile = inspect_txcap_profile(payload)
        if profile is not None:
            report["txcap_profile"] = profile
    return report


def read_chain_mask(text):
    if NVRAM_INTEGER.fullmatch(text) is None:
        return None
    base = 16 if text.lstrip("+-").lower().startswith("0x") else 10
    try:
        value = int(text, base)
    except ValueError:
        return None
    return value if 0 <= value <= 0xff else None


def inspect_nvram_topology(assignments, keys):
    flat = {key for key in keys if "/" not in key}
    slice_1 = {key for key in keys if key.startswith(SLICE_1_PREFIX)}
    arrays = Counter()
    masks = {key: set() for key in CHAIN_MASK_KEYS}
    for key, value in assignments:
        text = value.partition("#")[0].strip()
        if key in masks:
            masks[key].add(read_chain_mask(text))
        tokens = text.split(",")
        if len(tokens) > 1 and all(NVRAM_INTEGER.fullmatch(token.strip()) for token in tokens):
            arrays[len(tokens)] += 1

    return {
        "distinct_keys_by_namespace": {
            "flat": len(flat),
            "slice/1": len(slice_1),
            "other": len(keys) - len(flat) - len(slice_1),
        },
        "slice_1_keys_with_flat_leaf": sum(key[len(SLICE_1_PREFIX):] in flat for key in slice_1),
        "numeric_arrays_by_token_count": {str(length): count for length, count in arrays.items()},
        "chain_masks": {
            key: next(iter(values)) if len(values) == 1 else None for key, values in masks.items()
        },
    }


def inspect_nvram(path, include_topology=False):
    data, identity = read_artifact(path)
    assignments = []
    revisions = set()
    for line_number, line in enumerate(data.decode("ascii").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key:
            raise ValueError(f"Invalid NVRAM assignment on line {line_number}")
        assignments.append((key, value))
        if key == "sromrev" and value.strip().isdecimal():
            revisions.add(int(value))

    keys = {key for key, _ in assignments}
    report = {
        "file": identity,
        "encoding": "ASCII",
        "assignments": len(assignments),
        "distinct_keys": len(keys),
        "flat_key_assignments": sum("/" not in key for key, _ in assignments),
        "slice_1_assignments": sum(key.startswith(SLICE_1_PREFIX) for key, _ in assignments),
        "srom_revision": next(iter(revisions)) if len(revisions) == 1 else None,
    }
    if include_topology:
        report["topology"] = inspect_nvram_topology(assignments, keys)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clm", type=Path, help="Local Country Locale Matrix BLOB")
    parser.add_argument("--txcap", type=Path, help="Local TxCap BLOB")
    parser.add_argument("--nvram", type=Path, help="Local NVRAM text sidecar")
    parser.add_argument(
        "--nvram-topology",
        action="store_true",
        help="Include namespace counts, numeric array lengths and four chain masks with --nvram",
    )
    args = parser.parse_args()
    if args.nvram_topology and args.nvram is None:
        parser.error("--nvram-topology requires --nvram")
    if args.clm is None and args.txcap is None and args.nvram is None:
        parser.error("provide --clm, --txcap or --nvram")

    report = {}
    for role, path in (("clm", args.clm), ("txcap", args.txcap), ("nvram", args.nvram)):
        if path is None:
            continue
        try:
            if role == "nvram":
                report[role] = inspect_nvram(path, include_topology=args.nvram_topology)
            else:
                report[role] = inspect_blob(path, role)
        except (OSError, ValueError) as error:
            parser.error(f"{role} {path}: {error}")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
