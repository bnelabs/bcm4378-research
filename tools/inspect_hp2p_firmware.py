#!/usr/bin/env python3
"""Locate HP2P name records in local BCM4378 firmware images."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from struct import Struct
import sys

from inspect_firmware import read_artifact


# Linux brcmfmac uses this RAM origin for the flat BCM4378 payload.
RAM_ORIGIN = 0x352000
ENTRY_SIZE = 12
POINTER = Struct("<I")
RECORD_NAMES = (
    "hp2p_lfrag_rsrv",
    "hp2p_ll",
    "hp2p_txop",
    "hp2p_host_latency_cnt",
    "hp2p_dur",
)
LITERAL_NAMES = ("hp2p", "bus:hp2p_lfrag_rsrv", "hp2p_rxcmpl", "hp2p_txcmpl")


def match_offsets(payload, needle):
    offset = payload.find(needle)
    while offset != -1:
        yield offset
        offset = payload.find(needle, offset + 1)


def aligned_references(payload, text_offset):
    pointer = POINTER.pack(RAM_ORIGIN + text_offset)
    return [offset for offset in match_offsets(payload, pointer) if offset % POINTER.size == 0]


def matching_records(payload, start):
    end = start + len(RECORD_NAMES) * ENTRY_SIZE
    if end > len(payload):
        return None
    rows = []
    metadata = bytearray()
    for index, name in enumerate(RECORD_NAMES):
        offset = start + index * ENTRY_SIZE
        pointer = POINTER.unpack_from(payload, offset)[0] - RAM_ORIGIN
        if pointer < 0 or not payload.startswith(name.encode("ascii") + b"\0", pointer):
            return None
        rows.append({"name": name, "row_file_offset": offset, "string_file_offset": pointer})
        metadata.extend(payload[offset + POINTER.size:offset + ENTRY_SIZE])
    return {"rows": rows, "metadata_sha256": sha256(metadata).hexdigest()}


def inspect_image(payload):
    table_candidates = []
    # The first row can point inside the longer bus-prefixed string.
    for text_offset in match_offsets(payload, RECORD_NAMES[0].encode("ascii") + b"\0"):
        for offset in aligned_references(payload, text_offset):
            if table := matching_records(payload, offset):
                table_candidates.append(table)
    literal_references = {}
    for name in LITERAL_NAMES:
        literal_references[name] = [
            {
                "string_file_offset": offset,
                "aligned_reference_file_offsets": aligned_references(payload, offset),
            }
            for offset in match_offsets(payload, name.encode("ascii") + b"\0")
            if not offset or payload[offset - 1] == 0
        ]
    return {"table_candidates": table_candidates, "literal_references": literal_references}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, nargs="+")
    args = parser.parse_args()
    results = []
    try:
        for path in args.images:
            payload, identity = read_artifact(path)
            results.append({"file": identity, **inspect_image(payload)})
    except (OSError, ValueError) as error:
        print(f"Could not read the local firmware image: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "reference_ram_origin": hex(RAM_ORIGIN),
        "candidate_record_size": ENTRY_SIZE,
        "images": results,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
