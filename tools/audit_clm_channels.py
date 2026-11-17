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
LOCALE_LOOKUP = Struct("<48I")
DESCRIPTOR = Struct("<II")
CHANNEL_RANGE = Struct("<BBB")
RANGE_ENDPOINTS = Struct("<BB")
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
WIDTH_FROM_GROUP = {0: 20, 1: 40, 8: 80}
PRIMARY_OFFSETS = {20: (0,), 40: (-2, 2), 80: (-6, -2, 2, 6)}
BAND_TABLES = {
    "2.4 GHz": {20: "2.4ghz_primary", 40: "2.4ghz_40mhz_centers_inferred"},
    "5 GHz": {20: "5ghz_primary", 40: "5ghz_40mhz_centers_inferred", 80: "5ghz_80mhz_centers_inferred"},
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


def range_sets(records, ranges, label):
    sets = []
    cursor = 0
    while cursor < len(records):
        end = cursor + 1 + records[cursor]
        identifiers = records[cursor + 1:end]
        if end > len(records) or any(i >= len(ranges) for i in identifiers):
            raise ValueError(f"Invalid channel range set in {label}")
        sets.append([ranges[i] for i in identifiers])
        cursor = end
    return sets


def locale_stream(data, start, end, ranges, base_sets=None, restricted_sets=None):
    cursor = start
    locales = []
    while cursor < end:
        offset = cursor
        selected_ranges = []
        restricted_ranges = []
        if base_sets is not None:
            if cursor + 4 > end:
                raise ValueError(f"Truncated base locale at {offset:#x}")
            allowed_index, _, restricted_index, limit_count = data[cursor:cursor + 4]
            cursor += 4 + limit_count * 2
            if (
                cursor > end
                or allowed_index >= len(base_sets)
                or (restricted_index != 0xff and restricted_index >= len(restricted_sets))
                or any(i >= len(ranges[20]) for i in data[offset + 5:cursor:2])
            ):
                raise ValueError(f"Invalid base locale at {offset:#x}")
            selected_ranges = base_sets[allowed_index]
            if restricted_index != 0xff:
                restricted_ranges = restricted_sets[restricted_index]

        tx_ranges = {}
        while True:
            if cursor >= end:
                raise ValueError(f"Missing transmit group at {cursor:#x}")
            flags = data[cursor]
            count_offset = cursor + (2 if flags & 0x80 else 1)
            width = WIDTH_FROM_GROUP.get(flags & 0x49)
            if count_offset >= end or width is None:
                raise ValueError(f"Invalid transmit group at {cursor:#x}")
            # The firmware takes the row stride from bits 4–5 and continues when bit 2 is set.
            stride = 3 + ((flags >> 4) & 3)
            first = count_offset + 1
            cursor = first + data[count_offset] * stride
            identifiers = data[first + 1:cursor:stride]
            if cursor > end or any(i >= len(ranges[width]) for i in identifiers):
                raise ValueError(f"Invalid transmit records at {first:#x}")
            tx_ranges.setdefault(width, set()).update(
                ranges[width][i] for value, i in zip(data[first:cursor:stride], identifiers)
                if value != 0x80
            )
            if not flags & 4:
                break
        locales.append({
            "offset": offset,
            "base_ranges": selected_ranges,
            "restricted_ranges": restricted_ranges,
            "tx_ranges": tx_ranges,
        })
    return locales


def channel_blocks(channel_tables, base, extra, tables):
    blocks = {}
    allowed = {
        p for p in channel_tables[tables[20]]["channel_numbers"]
        if any(lo <= p <= hi for lo, hi in base["base_ranges"])
    }
    for width, table in tables.items():
        tx_ranges = base["tx_ranges"].get(width, set()) | extra["tx_ranges"].get(width, set())
        centers = []
        primaries = set()
        for center in channel_tables[table]["channel_numbers"]:
            members = {center + delta for delta in PRIMARY_OFFSETS[width]}
            if members <= allowed and any(lo <= center <= hi for lo, hi in tx_ranges):
                centers.append(center)
                primaries.update(members)
        blocks[width] = {"centers": centers, "primaries": sorted(primaries)}
    return blocks


def decode_locales(data, base, lookup_offset, region_rows, channel_tables, codes):
    dataset_offset(data, base, lookup_offset + base, LOCALE_LOOKUP.size, "Extended CLM lookup table")
    lookup = LOCALE_LOOKUP.unpack_from(data, lookup_offset)
    offsets = {
        slot: dataset_offset(data, base, lookup[slot], 1, f"CLM lookup slot {slot}")
        for slot in (2, 3, 4, 6, 7, 8, 9, 16, 17, 22)
    }
    ranges = {}
    range_sections = (
        (20, offsets[2], offsets[16]),
        (40, offsets[16], offsets[17]),
        (80, offsets[17], lookup_offset),
    )
    for width, first, end in range_sections:
        # Some 80 MHz arrays are padded to align the pointer table.
        if width == 80 and end % 4 == 0 and data[end - 2:end] == b"\x00\x00":
            end -= 2
        if end <= first or (end - first) % RANGE_ENDPOINTS.size:
            raise ValueError(f"Invalid {width} MHz channel ranges")
        ranges[width] = list(RANGE_ENDPOINTS.iter_unpack(data[first:end]))
        if any(not lo or hi < lo for lo, hi in ranges[width]):
            raise ValueError(f"Invalid {width} MHz channel range endpoints")

    # The first referenced row of slot 46 follows the restricted range sets.
    _, subchannel_descriptors = counted_records(data, base, lookup, 46, DESCRIPTOR.size)
    first_subchannel = min(
        dataset_offset(data, base, pointer, 1, "Subchannel table")
        for count, pointer in DESCRIPTOR.iter_unpack(subchannel_descriptors)
        if count
    )
    if not offsets[3] < first_subchannel or not offsets[4] < offsets[6] < offsets[8] < offsets[7] < offsets[9] < offsets[22]:
        raise ValueError("Unexpected CLM locale table order")
    allowed = range_sets(data[offsets[4]:offsets[6]], ranges[20], "slot 4")
    restricted = range_sets(data[offsets[3]:first_subchannel], ranges[20], "slot 3")
    streams = [
        locale_stream(data, offsets[6], offsets[8], ranges, allowed, restricted),
        locale_stream(data, offsets[7], offsets[9], ranges, allowed, restricted),
        locale_stream(data, offsets[8], offsets[7], ranges),
        locale_stream(data, offsets[9], offsets[22], ranges),
    ]
    for code, row in region_rows.items():
        if any(i >= len(stream) for i, stream in zip(row[3:7], streams)):
            raise ValueError(f"Invalid locale indices for {code}")

    selected = {}
    for code in codes:
        if code not in region_rows:
            raise ValueError(f"No CLM region row for {code}")
        row = region_rows[code]
        indices = row[3:7]
        bands = {}
        for n, (band, tables) in enumerate(BAND_TABLES.items()):
            base_locale = streams[n][indices[n]]
            width_locale = streams[n + 2][indices[n + 2]]
            bands[band] = {
                "base_locale_index": indices[n],
                "base_locale_offset": base_locale["offset"],
                "base_channel_ranges": base_locale["base_ranges"],
                "restricted_channel_ranges": base_locale["restricted_ranges"],
                "width_locale_index": indices[n + 2],
                "width_locale_offset": width_locale["offset"],
                "channel_blocks_by_width_mhz": channel_blocks(channel_tables, base_locale, width_locale, tables),
            }
        selected[code] = {"region_bytes_hex": row.hex(), "bands": bands}

    common = {}
    for band, widths in BAND_TABLES.items():
        common[band] = {
            width: sorted(set.intersection(*[
                set(s["bands"][band]["channel_blocks_by_width_mhz"][width]["centers"])
                for s in selected.values()
            ]))
            for width in widths
        }
    return {
        "region_rows_checked": len(region_rows),
        "locale_counts_by_lookup_slot": dict(zip((6, 7, 8, 9), map(len, streams))),
        "range_counts_by_width_mhz": {width: len(table) for width, table in ranges.items()},
        "regions": selected,
        "common_centers_by_band_and_width_mhz": common,
    }


def decode_dataset(data, region_code=None, locale_codes=()):
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
    result = {
        "dataset_virtual_base": base,
        "lookup_offset": lookup_offset,
        "channel_tables": channels,
        "region_directory": region,
        "creation": {"slot": 24, "offset": creation_offset, "text": creation},
        "dataset_sha256_excluding_creation_text": sha256(data[:creation_offset] + data[terminator:]).hexdigest(),
    }
    if locale_codes:
        result["locales"] = decode_locales(data, base, lookup_offset, by_code, channels, locale_codes)
    return result


def read_channel_profile(path, region_code=None, locale_codes=()):
    _, (primary, _), profile = read_profile(path)
    return {
        "path": str(path),
        "file_sha256": profile["sha256"],
        "metadata": profile["metadata"],
        **decode_dataset(primary, region_code, locale_codes),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+", help="Local stock BCM4378 .clmb files")
    parser.add_argument("--region-code", help="Include the raw row for this two-character code")
    parser.add_argument("--locale", action="append", default=[], metavar="CODE",
                        help="Decode channel blocks for this code. Repeat for a common-center comparison.")
    args = parser.parse_args()
    for code in [*args.locale, args.region_code]:
        if code is None:
            continue
        if not code.isascii() or not REGION_CODE.fullmatch(code.upper()):
            parser.error("Region codes must be two ASCII letters or digits")
    region_code = args.region_code.upper() if args.region_code is not None else None
    locale_codes = [code.upper() for code in args.locale]
    profiles = []
    for path in args.paths:
        try:
            profiles.append(read_channel_profile(path, region_code, locale_codes))
        except (OSError, RuntimeError, ValueError) as error:
            parser.error(f"{path}: {error}")
    print(json.dumps(profiles, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
