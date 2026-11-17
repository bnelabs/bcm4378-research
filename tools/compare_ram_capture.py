#!/usr/bin/env python3
"""Compare a retained brcmfmac PCIe RAM capture with a stock firmware file."""

import argparse
import json
from pathlib import Path
from struct import Struct

from inspect_firmware import MAX_ARTIFACT_SIZE, read_artifact
from inspect_hp2p_firmware import RAM_ORIGIN


LIVE_PATHS = (Path("/dev"), Path("/proc"), Path("/sys"))
UPSTREAM_TX_THREAD_ID = 0x54485244
# The stock ThreadX fault formatter loads these fields at offsets 0x00–0x14,
# 0x28 and 0x44. It prints the address of the embedded timer at offset 0x4c.
THREADX_FAULT_FIELDS = Struct("<6I16xI24xI")
THREADX_TIMER_OFFSET = 0x4C


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


def decode_threadx_fault(capture, prefix_bytes, timer_address):
    thread_address = timer_address - THREADX_TIMER_OFFSET
    relative_address = thread_address - RAM_ORIGIN
    record_start = prefix_bytes + relative_address
    if relative_address < 0 or relative_address % 4 or record_start + THREADX_FAULT_FIELDS.size > len(capture):
        raise ValueError("Thread fields derived from Timer address lie outside aligned captured BCM4378 RAM")

    thread_id, run_count, stack_ptr, stack_start, stack_end, stack_size, name_ptr, entry = (
        THREADX_FAULT_FIELDS.unpack_from(capture, record_start)
    )
    name = None
    name_start = prefix_bytes + name_ptr - RAM_ORIGIN
    if prefix_bytes <= name_start < len(capture):
        terminator = capture.find(b"\0", name_start, min(name_start + 128, len(capture)))
        if terminator > name_start:
            raw_name = capture[name_start:terminator]
            if all(0x20 <= value <= 0x7E for value in raw_name):
                name = raw_name.decode("ascii")
    return {
        "reference_ram_base": hex(RAM_ORIGIN),
        "thread_address_from_timer": hex(thread_address),
        "capture_file_offset": record_start,
        "id_raw": hex(thread_id),
        "id_matches_public_threadx_tag": thread_id == UPSTREAM_TX_THREAD_ID,
        "run_count": run_count,
        "stack_pointer": hex(stack_ptr),
        "stack_start": hex(stack_start),
        "stack_end": hex(stack_end),
        "stack_size_bytes": stack_size,
        "name_pointer": hex(name_ptr),
        "name_if_captured": name,
        "entry_function_pointer": hex(entry),
        "timer_address_from_fault_log": hex(timer_address),
    }


def compare(capture_path, firmware_path, ram_bytes, save_restore_bytes, prefix_bytes, threadx_timer=None):
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

    result = {
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
    if threadx_timer is not None:
        result["threadx_fault_record"] = decode_threadx_fault(capture, prefix_bytes, threadx_timer)
    return result


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
    parser.add_argument("--threadx-timer", type=byte_count,
                        help="Timer address printed by THREADX TRAP INFO in a paired BCM4378 fault log")
    args = parser.parse_args()
    try:
        result = compare(
            args.capture, args.firmware, args.ram_bytes, args.save_restore_bytes, args.prefix_bytes,
            threadx_timer=args.threadx_timer,
        )
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
