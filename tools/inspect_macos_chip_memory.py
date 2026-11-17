#!/usr/bin/env python3
"""Inspect the BCM4378 memory descriptors in an installed AppleBCMWLAN executable."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from struct import Struct, error as StructError, unpack_from
import subprocess
import sys

from inspect_firmware import read_artifact


INITIALIZER = "__ZN31AppleBCMWLANChipManagerPCIe437812initWithChipEjh"
CHIP_MANAGER = r"__ZN27AppleBCMWLANChipManagerPCIe\d+set"
ARCH_BY_SUBTYPE = {0x80000002: "arm64e", 0x8000000c: "arm64e.x1"}
TABLE_LOAD = re.compile(
    r"adrp\tx1, \d+ ; (0x[\da-f]+)\n[^\n]*add\tx1, x1, #(0x[\da-f]+)\n"
    r"[^\n]*mov\tx0, x19\n(?:[^\n]*mov\tw2, #(0x[\da-f]+)\n)?"
    rf"[^\n]*bl\t{CHIP_MANAGER}(\w+?)E"
)
REGION = Struct("<III")
WINDOW = Struct("<IIIII")
UCODE_DIAGNOSTIC = Struct("<IIII")


def driver_slices(payload):
    magic, count = unpack_from(">II", payload)
    if magic != 0xcafebabe or count != 2:
        raise ValueError("Expected a universal AppleBCMWLAN executable with two slices")
    slices = {}
    for index in range(count):
        cpu, subtype, offset, size, _ = unpack_from(">IIIII", payload, 8 + index * 20)
        if cpu != 0x0100000c or subtype not in ARCH_BY_SUBTYPE or offset + size > len(payload):
            raise ValueError("Unsupported or truncated Apple silicon slice")
        slices[ARCH_BY_SUBTYPE[subtype]] = payload[offset:offset + size]
    if len(slices) != count:
        raise ValueError("Repeated Apple silicon slice")
    return slices


def file_backed_segments(payload):
    magic = unpack_from("<I", payload)[0]
    count, command_bytes = unpack_from("<II", payload, 16)
    end = 32 + command_bytes
    if magic != 0xfeedfacf or end > len(payload) or count > command_bytes // 8:
        raise ValueError("Invalid Mach-O load commands")
    segments = []
    position = 32
    for _ in range(count):
        command, length = unpack_from("<II", payload, position)
        if length < 8 or position + length > end:
            raise ValueError("Invalid Mach-O command length")
        if command == 0x19:
            if length < 72:
                raise ValueError("Truncated Mach-O segment")
            address, _, offset, size = unpack_from("<QQQQ", payload, position + 24)
            if offset + size > len(payload):
                raise ValueError("Mach-O segment exceeds its slice")
            if size:
                segments.append((address, offset, size))
        position += length
    return segments


def inspect_slice(executable, arch, payload):
    segments = file_backed_segments(payload)
    instructions = subprocess.check_output(
        ("xcrun", "llvm-objdump", "--macho", f"--arch={arch}", "--disassemble",
         "--dis-symname", INITIALIZER, executable),
        text=True,
        timeout=15,
    )
    table_addresses = {
        (name, selector): int(page, 16) + int(offset, 16)
        for page, offset, selector, name in TABLE_LOAD.findall(instructions)
    }

    def read_table(name, row_format, count, selector=""):
        address = table_addresses[name, selector]
        byte_count = row_format.size * count
        for base, file_offset, size in segments:
            relative = address - base
            if 0 <= relative <= size - byte_count:
                start = file_offset + relative
                return list(row_format.iter_unpack(payload[start:start + byte_count]))
        raise ValueError(f"Table {name} is outside the file-backed Mach-O segments")

    def descriptor_count(name):
        match = re.search(
            rf"mov\tw1, #(0x[\da-f]+)\n[^\n]*bl\t{CHIP_MANAGER}{name}CountEj",
            instructions,
        )
        if match is None or not 0 < int(match[1], 16) <= 256:
            raise ValueError(f"Unsupported {name} descriptor count")
        return int(match[1], 16)

    core = read_table("CoreRegionList", REGION, descriptor_count("Core"))
    wrappers = read_table("WrapperRegionList", REGION, descriptor_count("Wrapper"))
    windows = read_table("BackplaneWindows", WINDOW, descriptor_count("BackplaneWindow"))
    memory = {
        identifier - 0x20000: (base, length)
        for identifier, base, length in read_table("MemoryRegionList", REGION, descriptor_count("Memory"))
    }
    if memory.keys() != set(range(7)):
        raise ValueError("Unsupported BCM4378 memory region selectors")

    ram_base, ram_length = memory[4]
    view_length, first_length = memory[0][1], memory[1][1]
    prefix_length, low_ram_length = memory[2][1], memory[5][1]
    high_ram_length = memory[6][1]
    return {
        "core_region_sizes_bytes": dict(Counter(length for _, _, length in core)),
        "wrapper_region_sizes_bytes": dict(Counter(length for _, _, length in wrappers)),
        "backplane_windows": {
            "fixed": sum(row[2] == 0 for row in windows),
            "remappable_core": sum(row[0] == 0 and row[2] != 0 for row in windows),
            "remappable_wrapper": sum(row[0] == 1 and row[2] != 0 for row in windows),
        },
        "memory_region_sizes_bytes": {selector: length for selector, (_, length) in memory.items()},
        "firmware_ram_bytes": ram_length,
        "arm_ram_base_matches_linux_reference": ram_base == 0x352000,
        "firmware_ram_split_into_adjacent_regions": (
            memory[5][0] == ram_base
            and memory[6][0] == ram_base + low_ram_length
            and low_ram_length + high_ram_length == ram_length
        ),
        "first_region_split_into_adjacent_regions": (
            memory[2][0] == memory[1][0]
            and memory[3][0] == memory[1][0] + prefix_length
            and prefix_length + memory[3][1] == first_length
        ),
        "coexistence_view_and_first_region_share_base": memory[0][0] == memory[1][0],
        "coexistence_view_length_equals_first_region_plus_ram": view_length == first_length + ram_length,
        "microcode_diagnostic_size_fields": {
            "scratch": read_table("UCodeRegionInfo", UCODE_DIAGNOSTIC, 1, "0x0")[0][0],
            "shared": read_table("UCodeRegionInfo", UCODE_DIAGNOSTIC, 1, "0x1")[0][0],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    try:
        payload, info = read_artifact(args.executable)
        slices = {
            arch: inspect_slice(info["resolved_path"], arch, data)
            for arch, data in driver_slices(payload).items()
        }
    except (OSError, ValueError, StructError, KeyError, subprocess.SubprocessError) as error:
        print(f"Could not inspect the BCM4378 driver memory tables: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"driver": info, "slices": slices}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
