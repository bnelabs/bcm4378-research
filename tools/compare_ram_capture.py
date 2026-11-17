#!/usr/bin/env python3
"""Compare a retained brcmfmac PCIe RAM capture with a stock firmware file."""

import argparse
import json
from pathlib import Path

from inspect_firmware import MAX_ARTIFACT_SIZE, read_artifact


LIVE_PATHS = (Path("/dev"), Path("/proc"), Path("/sys"))


def retained_path(path):
    resolved = path.resolve(strict=True)
    if any(resolved == root or root in resolved.parents for root in LIVE_PATHS) or not resolved.is_file():
        raise ValueError(f"Supply an ordinary retained file at {path}")
    return resolved


def read_capture(path, expected_bytes):
    resolved = retained_path(path)
    actual_bytes = resolved.stat().st_size
    if actual_bytes != expected_bytes:
        raise ValueError(f"Capture has {actual_bytes} bytes, expected {expected_bytes} from the declared layout")
    with resolved.open("rb") as file:
        data = file.read(expected_bytes + 1)
    if len(data) != expected_bytes:
        raise ValueError("Capture size changed during the read")
    return data


def compare(capture_path, firmware_path, ram_bytes, save_restore_bytes, prefix_bytes):
    if not 0 <= save_restore_bytes < ram_bytes:
        raise ValueError("Save/restore bytes must be smaller than total RAM")
    dumpable_bytes = ram_bytes - save_restore_bytes
    expected_bytes = prefix_bytes + dumpable_bytes
    if prefix_bytes < 0 or expected_bytes > MAX_ARTIFACT_SIZE:
        raise ValueError("Capture layout must fit in 64 MiB with a nonnegative prefix length")

    firmware, identity = read_artifact(retained_path(firmware_path))
    if len(firmware) > dumpable_bytes:
        raise ValueError("Firmware image exceeds the declared captured RAM range")
    capture = read_capture(capture_path, expected_bytes)
    uploaded_extent = memoryview(capture)[prefix_bytes:prefix_bytes + len(firmware)]
    equal_bytes = sum(expected == observed for expected, observed in zip(firmware, uploaded_extent))

    return {
        "ram_bytes": ram_bytes,
        "save_restore_bytes": save_restore_bytes,
        "dumpable_ram_bytes": dumpable_bytes,
        "capture_bytes": len(capture),
        "event_prefix_bytes": prefix_bytes,
        "reference_firmware": {"bytes": identity["bytes"], "sha256": identity["sha256"]},
        "uploaded_extent": {
            "same_offset_equal_bytes": equal_bytes,
            "different_bytes": len(firmware) - equal_bytes,
            "full_reference_match": equal_bytes == len(firmware),
        },
        "remaining_captured_ram_bytes": dumpable_bytes - len(firmware),
    }


def byte_count(value):
    """Accept decimal byte counts and the 0x notation used in kernel logs."""
    return int(value, 16 if value.lower().startswith("0x") else 10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("firmware", type=Path)
    parser.add_argument("--ram-bytes", type=byte_count, required=True, help="Total bytes reported by the driver")
    parser.add_argument("--save-restore-bytes", type=byte_count, required=True,
                        help="Bytes excluded by the driver for save/restore")
    parser.add_argument("--prefix-bytes", type=byte_count, default=0,
                        help="Event data length recorded by the producer, zero for a direct capture")
    args = parser.parse_args()
    try:
        result = compare(args.capture, args.firmware, args.ram_bytes, args.save_restore_bytes, args.prefix_bytes)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
