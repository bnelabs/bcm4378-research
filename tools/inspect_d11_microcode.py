#!/usr/bin/env python3
"""Identify the stock BCM4378 D11 loader and compare a saved microcode readback."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from struct import Struct

from compare_ram_capture import read_capture
from inspect_firmware import (
    BCM4378_RAM_BASE,
    FIRMWARE_TAG,
    THUMB_WORD,
    WORD_PAIR,
    inspect_embedded_metadata,
    read_artifact,
    thumb_wide_branch_offset,
)


HALFWORD = Struct("<H")
WORD = Struct("<I")

# Observed Thumb sequences in Honshu, Capri and Kyushu. Call instructions
# with build-dependent displacements are decoded separately.
SELECTOR_ENTRY = bytes.fromhex("83 6c 13 b5 04 46 7b b9 10 4b 11 49 1a 68 20 46")
SELECTOR_CASE_ONE = bytes.fromhex("01 2b 03 d1 09 4b 0a 49 1a 68 ec e7")
WRITER_ENTRY = bytes.fromhex("70 b5 15 46 06 46 0c 46")
WRITER_BODY = bytes.fromhex(
    "0c 4b ad 08 1b 68 3b b9 d6 f8 8c 30 4f f0 40 72 c3 f8 60 21 "
    "d3 f8 60 31 21 46 04 eb 85 05 a9 42 00 d1 70 bd d6 f8 8c 30 "
    "51 f8 04 2b c3 f8 64 21 f5 e7 00 bf"
)
CACHE_ENTRY = bytes.fromhex("83 6c 03 48 40 f8 23 10 02 49 41 f8 23 20 70 47")


def section(data, offset, size):
    if offset < 0 or offset + size > len(data):
        raise ValueError("D11 loader reference lies outside the mapped firmware image")
    return data[offset:offset + size]


def literal_at(data, instruction, register):
    # Thumb LDR (literal) T1 uses Align(PC, 4) and an eight-bit word offset.
    value, = HALFWORD.unpack(section(data, instruction, HALFWORD.size))
    if value >> 8 != (0x48 | register):
        raise ValueError(f"Expected a Thumb literal load into r{register} at file offset {instruction:#x}")
    literal = ((instruction + 4) & ~3) + (value & 0xff) * WORD.size
    return WORD.unpack(section(data, literal, WORD.size))[0]


def call_target(data, instruction):
    first, second = THUMB_WORD.unpack(section(data, instruction, THUMB_WORD.size))
    if second & 0xd000 != 0xd000:
        raise ValueError(f"Expected a Thumb BL at file offset {instruction:#x}")
    displacement = thumb_wide_branch_offset(first, second ^ 0x4000)
    if displacement is None:
        raise ValueError(f"Invalid Thumb BL at file offset {instruction:#x}")
    return instruction + 4 + displacement


def read_component(data, unit, address, size_address):
    start = address - BCM4378_RAM_BASE
    boundary = size_address - BCM4378_RAM_BASE
    size, = WORD.unpack(section(data, boundary, WORD.size))
    if size == 0 or size % 8 or start + size != boundary:
        raise ValueError(f"Invalid D11 component length or boundary for unit {unit}")
    component = section(data, start, size)
    if any(component[7::8]):
        raise ValueError(f"Unrecognized D11 instruction record layout for unit {unit}")
    used_records = (len(component.rstrip(b"\0")) + 7) // 8
    if not used_records:
        raise ValueError(f"Empty D11 component for unit {unit}")
    return {
        "unit": unit,
        "component_file_offset": start,
        "size_field_file_offset": boundary,
        "bytes": size,
        "word_stores_if_transfer_completes": size // WORD.size,
        "eight_byte_records_before_zero_padding": used_records,
        "zero_padding_records": size // 8 - used_records,
        "sha256": sha256(component).hexdigest(),
    }, component


def inspect_loader(data):
    tags = list(FIRMWARE_TAG.finditer(data))
    if len(tags) != 1 or not tags[0]["build"].startswith(b"4378"):
        raise ValueError("Expected a BCM4378 stock firmware tag")
    candidates = [
        m.start() for m in re.finditer(re.escape(SELECTOR_ENTRY), data)
        if m.start() % 2 == 0 and data[m.start() + 0x28:m.start() + 0x34] == SELECTOR_CASE_ONE
    ]
    if len(candidates) != 1:
        raise ValueError("Expected one matching BCM4378 D11 image selector")
    selector = candidates[0]
    writer = call_target(data, selector + 0x10)
    if (section(data, writer, len(WRITER_ENTRY)) != WRITER_ENTRY
            or section(data, writer + 0x0c, len(WRITER_BODY)) != WRITER_BODY):
        raise ValueError("Unrecognized D11 object-memory writer")
    cache = call_target(data, writer + 8)
    if section(data, cache, len(CACHE_ENTRY)) != CACHE_ENTRY:
        raise ValueError("Unrecognized D11 source cache writer")

    regions = [
        read_component(data, unit, literal_at(data, selector + source, 1),
                       literal_at(data, selector + count, 3))
        for unit, source, count in [(0, 0x0a, 0x08), (1, 0x2e, 0x2c)]
    ]
    main, auxiliary = [r[0] for r in regions]
    if (main["bytes"] != auxiliary["bytes"]
            or auxiliary["size_field_file_offset"] + WORD.size != main["component_file_offset"]):
        raise ValueError("D11 components do not have the observed adjoining layout")

    guard = literal_at(data, writer + 0x0c, 3) - BCM4378_RAM_BASE
    source_table = literal_at(data, cache + 2, 0) - BCM4378_RAM_BASE
    size_table = literal_at(data, cache + 8, 1) - BCM4378_RAM_BASE
    report = {
        "reference_ram_base": hex(BCM4378_RAM_BASE),
        "firmware_id": tags[0]["firmware_id"].decode("ascii"),
        "microcode_build": inspect_embedded_metadata(data)["ucode_tags"],
        "selector_file_offset": selector,
        "object_writer_file_offset": writer,
        "source_cache_writer_file_offset": cache,
        "object_memory_transfer": {
            "context_register_pointer_offset": 0x8c,
            "unit_field_offset": 0x48,
            "object_address_register_offset": 0x160,
            "object_data_register_offset": 0x164,
            "address_setup_value": hex(0x03000000),
            "address_setup_guard_file_offset": guard,
            "address_setup_guard_stock_value": WORD.unpack(section(data, guard, WORD.size))[0],
        },
        "source_cache": {
            "pointer_table_file_offset": source_table,
            "size_table_file_offset": size_table,
            "stock_source_pointers": WORD_PAIR.unpack(section(data, source_table, WORD_PAIR.size)),
            "stock_source_sizes": WORD_PAIR.unpack(section(data, size_table, WORD_PAIR.size)),
        },
        "core_units": [r[0] for r in regions],
    }
    return report, [r[1] for r in regions]


def compare_readback(data, component):
    differences = [
        index for index, (actual, expected) in enumerate(zip(WORD.iter_unpack(data), WORD.iter_unpack(component)))
        if actual != expected
    ]
    return {
        "exact_match": not differences,
        "different_32bit_words": len(differences),
        "first_different_word": differences[0] if differences else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware", type=Path, help="Local stock BCM4378 .trx")
    parser.add_argument("--readback", type=Path,
                        help="Retained little-endian D11 program readback starting at object word zero")
    args = parser.parse_args()
    try:
        data, identity = read_artifact(args.firmware)
        report, components = inspect_loader(data)
        report["file"] = identity
        if args.readback:
            captured = read_capture(args.readback, len(components[0]))
            report["readback"] = {
                "bytes": len(captured),
                "sha256": sha256(captured).hexdigest(),
                "comparisons": [
                    {"unit": unit, **compare_readback(captured, component)}
                    for unit, component in enumerate(components)
                ],
            }
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
