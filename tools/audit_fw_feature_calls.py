#!/usr/bin/env python3
"""Read direct feature-bit updates from the AppleBCMWLAN extended parser."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
from struct import error as StructError
import subprocess
import sys

from inspect_firmware import read_artifact
from inspect_macos_chip_memory import driver_slices


PARSER = "__ZN16AppleBCMWLANCore17processFwFeaturesER19IO80211BufferCursormm"
FLAG_OPERATIONS = {
    "__ZN16AppleBCMWLANCore17featureFlagSetBitEi": "set",
    "__ZN16AppleBCMWLANCore19featureFlagClearBitEi": "clear",
}
INSTRUCTION = re.compile(
    r"([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+){4}(\S+)(?:\s+([^;]*?))?\s*(?:;.*)?"
)
LITERAL_ARGUMENT = re.compile(r"w1, #(0x[0-9a-f]+|[0-9]+)")
CONDITIONAL_BRANCHES = {"cbz", "cbnz", "tbz", "tbnz"}
NO_FALLTHROUGH = {
    "b", "br", "braa", "braaz", "brab", "brabz", "brk",
    "ret", "retaa", "retab", "retabsp", "retabspc",
}


def collect_predecessors(instructions):
    predecessors = defaultdict(list)
    for address, (opcode, operands) in instructions.items():
        if opcode == "b" or opcode.startswith("b.") or opcode in CONDITIONAL_BRANCHES:
            destination = operands.rsplit(",", 1)[-1].strip()
            if destination.startswith("0x"):
                target = int(destination, 16)
                if target in instructions:
                    predecessors[target].append(address)
        if opcode not in NO_FALLTHROUGH and address + 4 in instructions:
            predecessors[address + 4].append(address)
    return predecessors


def reaching_arguments(callsite, instructions, predecessors):
    # This routine uses literal arguments and branches to shared callsites.
    pending = list(predecessors[callsite])
    visited = set()
    arguments = set()
    while pending:
        address = pending.pop()
        if address in visited:
            continue
        visited.add(address)
        opcode, operands = instructions[address]
        if opcode == "b" and predecessors[address]:
            pending.extend(predecessors[address])
            continue
        literal = LITERAL_ARGUMENT.fullmatch(operands) if opcode == "mov" else None
        if not literal:
            raise ValueError(f"Unresolved feature argument at {address:#x} for {callsite:#x}")
        arguments.add(int(literal[1], 0))
    if not arguments:
        raise ValueError(f"No feature arguments reached {callsite:#x}")
    return sorted(arguments)


def parse_flag_updates(disassembly):
    _, symbol, body = disassembly.partition(f"\n{PARSER}:\n")
    if not symbol:
        raise ValueError("Missing extended feature parser in disassembly")
    instructions = {}
    for line in body.splitlines():
        match = INSTRUCTION.fullmatch(line.strip())
        if not match:
            if line.strip():
                raise ValueError(f"Unexpected parser disassembly line: {line}")
            continue
        address, opcode, operands = match.groups()
        instructions[int(address, 16)] = (opcode, operands or "")

    predecessors = collect_predecessors(instructions)
    updates = {"set": {}, "clear": {}}
    for address, (opcode, operands) in instructions.items():
        if opcode in {"bl", "b"} and operands in FLAG_OPERATIONS:
            operation = FLAG_OPERATIONS[operands]
            updates[operation][address] = reaching_arguments(address, instructions, predecessors)
    if not all(updates.values()):
        raise ValueError("Expected direct set and clear calls in the extended parser")
    return {
        operation: {
            "direct_calls": len(sites),
            "indices": sorted({bit for bits in sites.values() for bit in bits}),
            "shared_callsites": [
                {"address": hex(address), "indices": bits}
                for address, bits in sites.items()
                if len(bits) > 1
            ],
        }
        for operation, sites in updates.items()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    try:
        payload, info = read_artifact(args.executable)
        slices = {}
        for arch in driver_slices(payload):
            assembly = subprocess.check_output(
                ("xcrun", "llvm-objdump", "--macho", f"--arch={arch}", "--disassemble",
                 "--dis-symname", PARSER, info["resolved_path"]),
                text=True,
                timeout=15,
            )
            slices[arch] = parse_flag_updates(assembly)
    except (OSError, ValueError, StructError, subprocess.SubprocessError) as error:
        print(f"Could not audit AppleBCMWLAN feature calls: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"driver": info, "slices": slices}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
