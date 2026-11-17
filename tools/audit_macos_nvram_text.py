#!/usr/bin/env python3
"""Compare stock NVRAM text with the modeled macOS 26B131 normalization stage."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re

from inspect_firmware import read_artifact
from inventory_board_profiles import REVISIONS, resolve_local


REMOVED_PREFIXES = (b"macaddr", b"nocrc", b"il0macaddr", b"nvramver", b"moduleid")
AUDITED_KEYS = (
    b"olpc_thresh2g", b"olpc_thresh5g", b"olpc_anchor2g", b"olpc_anchor5g",
    b"slice/1/olpc_thresh2g", b"slice/1/olpc_thresh2g ", b"slice/1/olpc_anchor2g",
)


def inspect_text(data):
    # The replay covers the grammar observed in the installed BCM4378 profiles.
    if not data.endswith(b"\n") or any(byte != 10 and not 32 <= byte < 127 for byte in data):
        raise ValueError("Expected LF-terminated printable ASCII text")
    source = data[:-1].split(b"\n")
    if any(b"=" not in line or b"#" in line for line in source):
        raise ValueError("Expected assignment records without comments")

    cleaned = [re.sub(rb" +", b" ", line.strip(b" ")) for line in source]
    records = [line for line in cleaned if not line.startswith(REMOVED_PREFIXES)]
    if not records:
        raise ValueError("Expected at least one retained assignment")
    normalized = b"\0".join(records) + b"\0\0"
    keys = Counter(line.partition(b"=")[0] for line in records)
    return {
        "stock_records": len(source),
        "modeled_normalized_records": len(records),
        "modeled_normalized_bytes": len(normalized),
        "modeled_normalized_sha256": sha256(normalized).hexdigest(),
        "modeled_output_matches_lf_replacement_and_final_nul": normalized == data.replace(b"\n", b"\0") + b"\0",
        "modeled_exact_keys": {key.decode("ascii"): keys[key] for key in AUDITED_KEYS},
    }


def inventory(directory):
    root = directory.resolve(strict=True)
    profiles = {}
    targets = {}
    for revision in REVISIONS:
        stepping = root / f"C-4378__s-{revision}"
        if not stepping.is_dir():
            continue
        resolve_local(stepping, root)
        for path in sorted(stepping.glob("*.txt")):
            target = resolve_local(path, root)
            if target not in targets:
                data, identity = read_artifact(target)
                digest = identity["sha256"]
                targets[target] = digest
                if digest not in profiles:
                    profiles[digest] = {
                        "sha256": digest,
                        "stock_bytes": len(data),
                        "name_count_by_stepping": Counter(),
                        **inspect_text(data),
                    }
            profiles[targets[target]]["name_count_by_stepping"][revision] += 1
    if not profiles:
        raise ValueError(f"No BCM4378 text profiles found under {directory}")
    return {
        "scope": "Static model of the macOS 26B131 normalizer on retained BCM4378 text profiles",
        "name_count": sum(sum(row["name_count_by_stepping"].values()) for row in profiles.values()),
        "unique_payload_count": len(profiles),
        "profiles": sorted(profiles.values(), key=lambda row: row["sha256"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware_directory", type=Path)
    args = parser.parse_args()
    try:
        report = inventory(args.firmware_directory)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
