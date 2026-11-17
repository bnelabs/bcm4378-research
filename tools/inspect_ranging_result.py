#!/usr/bin/env python3
"""Decode one saved AppleBCMWLAN proximity-ranging result record."""

import argparse
import json
from pathlib import Path
from struct import Struct

from inspect_firmware import read_artifact


HEADER = Struct("<HH")
SESSION_FIELDS = Struct("<HHi6xh")
DISTANCE_FIELDS = Struct("<I2xBBHH")
# Version, minimum value length, session offset, and distance offset in build 26B131.
LAYOUTS = {
    0x203: (1, 128, 0x00, 0x44),
    0x208: (2, 96, 0x04, 0x1c),
    0x209: (3, 44, 0x04, 0x1c),
}


def distance_values(result_type, flags, raw):
    # Broadcom's published driver treats this value as unavailable.
    if raw == 0xffffffff:
        return None, None, "unavailable_marker"
    signed = raw - (1 << 32) if raw >= (1 << 31) else raw
    if result_type == 0x208 and flags & 0x80:
        signed = -signed
    scaled = signed * 1000
    if not -(1 << 31) <= scaled < (1 << 31):
        return None, None, "driver_conversion_overflow"
    return signed / 256, scaled >> 8, None


def decode_result(record):
    if len(record) < HEADER.size:
        raise ValueError("Truncated ranging result header")
    result_type, length = HEADER.unpack_from(record)
    if result_type not in LAYOUTS:
        raise ValueError(f"Unsupported ranging result type 0x{result_type:x}")
    version, minimum, session_offset, distance_offset = LAYOUTS[result_type]
    if length < minimum:
        raise ValueError(f"Ranging result v{version} needs at least {minimum} value bytes")
    end = HEADER.size + length
    padded_end = (end + 3) & ~3
    if len(record) not in (end, padded_end):
        raise ValueError("Expected one complete ranging result, with optional padding to a four-byte boundary")

    value = memoryview(record)[HEADER.size:end]
    session, flags, status, state = SESSION_FIELDS.unpack_from(value, session_offset)
    raw, valid, ftm_count, burst, rtt_count = DISTANCE_FIELDS.unpack_from(value, distance_offset)
    meters, millimeters, issue = distance_values(result_type, flags, raw)
    return {
        "type": f"0x{result_type:x}",
        "version": version,
        "value_bytes": length,
        "session_id": session,
        "flags": flags,
        "status": status,
        "state": state,
        "raw_average_distance_q8": raw,
        "average_distance_m": meters,
        "driver_distance_mm": millimeters,
        "distance_issue": issue,
        "valid_samples": valid,
        "ftm_frames": ftm_count,
        "burst_number": burst,
        "rtt_samples": rtt_count,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, help="Saved little-endian type, length and value bytes")
    args = parser.parse_args()
    try:
        record, _ = read_artifact(args.record)
        result = decode_result(record)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
