#!/usr/bin/env python3
"""Read channel and region tables from stock BCM4378 CLM files."""

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from struct import Struct

from audit_clm_profiles import read_profile
from inspect_radio_sidecars import CLM_HEADER


LOOKUP = Struct("<29I")
DESCRIPTOR = Struct("<II")
CHANNEL_RANGE = Struct("<BBB")
REGION_RECORD_SIZE = 9
REGION_CODE = re.compile("[A-Z0-9]{2}")
TIMESTAMP_SIZE = 20
CHANNEL_SLOTS = {
    "2.4ghz_primary": 0,
    "5ghz_primary": 1,
    "2.4ghz_40mhz_centers_inferred": 25,
    "5ghz_40mhz_centers_inferred": 26,
    "5ghz_80mhz_centers_inferred": 27,
    "slot_28": 28,
}


def dataset_offset(data, base, pointer, size, label):
    offset = pointer - base
    if not pointer or offset < CLM_HEADER.size or offset + size > len(data):
        raise ValueError(f"{label} lies outside the CLM dataset body")
    return offset


def counted_records(data, base, lookup, slot, record_size):
    label = f"CLM lookup slot {slot}"
    descriptor = dataset_offset(data, base, lookup[slot], DESCRIPTOR.size, label)
    count, pointer = DESCRIPTOR.unpack_from(data, descriptor)
    size = count * record_size
    records_offset = None
    records = b""
    if count:
        records_offset = dataset_offset(data, base, pointer, size, f"{label} records")
        records = data[records_offset:records_offset + size]
    elif pointer:
        raise ValueError(f"{label} has an empty list with a nonzero pointer")
    return {
        "slot": slot,
        "descriptor_offset": descriptor,
        "records_offset": records_offset,
        "count": count,
    }, records


def decode_dataset(data, region_code=None):
    if len(data) < CLM_HEADER.size:
        raise ValueError("Truncated CLM dataset header")
    magic, version, _, _, _, base, pointer, _, _ = CLM_HEADER.unpack_from(data)
    if magic != b"CLM DATA" or version != 0x00150000:
        raise ValueError("Expected the stock BCM4378 CLM version prefix")
    lookup_offset = dataset_offset(data, base, pointer, LOOKUP.size, "CLM lookup table")
    lookup = LOOKUP.unpack_from(data, lookup_offset)
    if lookup[13] != 0xA48150FF:
        raise ValueError("Unrecognized stock BCM4378 CLM lookup layout")

    channels = {}
    for name, slot in CHANNEL_SLOTS.items():
        table, records = counted_records(data, base, lookup, slot, CHANNEL_RANGE.size)
        ranges = list(CHANNEL_RANGE.iter_unpack(records))
        numbers = set()
        for first, last, step in ranges:
            if not first or last < first or not step or (last - first) % step:
                raise ValueError(f"Unexpected channel range in CLM lookup slot {slot}")
            numbers.update(range(first, last + 1, step))
        table["ranges"] = [{"first": first, "last": last, "step": step} for first, last, step in ranges]
        table["channel_numbers"] = sorted(numbers)
        channels[name] = table

    region, records = counted_records(data, base, lookup, 10, REGION_RECORD_SIZE)
    rows = [records[i:i + REGION_RECORD_SIZE] for i in range(0, len(records), REGION_RECORD_SIZE)]
    by_code = {row[:2].decode("ascii"): row for row in rows}
    if (
        not by_code
        or len(by_code) != region["count"]
        or any(not REGION_CODE.fullmatch(code) for code in by_code)
    ):
        raise ValueError("Unexpected code directory in CLM lookup slot 10")
    region["record_size"] = REGION_RECORD_SIZE
    region["records_sha256"] = sha256(records).hexdigest()
    region["codes"] = sorted(by_code)
    if region_code is not None:
        row = by_code.get(region_code)
        region["selected"] = None if row is None else {"code": region_code, "bytes_hex": row.hex()}

    creation_offset = dataset_offset(data, base, lookup[24], TIMESTAMP_SIZE, "CLM creation timestamp")
    terminator = creation_offset + TIMESTAMP_SIZE - 1
    if data[terminator] != 0:
        raise ValueError("Expected a null-terminated CLM creation timestamp")
    creation = data[creation_offset:terminator].decode("ascii")
    datetime.strptime(creation, "%Y-%m-%d %H:%M:%S")
    return {
        "dataset_virtual_base": base,
        "lookup_offset": lookup_offset,
        "channel_tables": channels,
        "region_directory": region,
        "creation": {"slot": 24, "offset": creation_offset, "text": creation},
        "dataset_sha256_excluding_creation_text": sha256(data[:creation_offset] + data[terminator:]).hexdigest(),
    }


def read_channel_profile(path, region_code=None):
    _, (primary, _), profile = read_profile(path)
    return {
        "path": str(path),
        "file_sha256": profile["sha256"],
        "metadata": profile["metadata"],
        **decode_dataset(primary, region_code),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+", help="Local stock BCM4378 .clmb files")
    parser.add_argument("--region-code", help="Include the raw row for this two-character code")
    args = parser.parse_args()
    region_code = args.region_code
    if region_code is not None:
        if not region_code.isascii() or not REGION_CODE.fullmatch(region_code.upper()):
            parser.error("--region-code must be two ASCII letters or digits")
        region_code = region_code.upper()
    profiles = []
    for path in args.paths:
        try:
            profiles.append(read_channel_profile(path, region_code))
        except (OSError, RuntimeError, ValueError) as error:
            parser.error(f"{path}: {error}")
    print(json.dumps(profiles, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
