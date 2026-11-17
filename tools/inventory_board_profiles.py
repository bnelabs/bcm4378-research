#!/usr/bin/env python3
"""Inventory installed BCM4378 firmware names and payload identities as JSON."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


REVISIONS = ("B1", "B3")
EXTENSIONS = (".trx", ".clmb", ".txcb", ".txt")


def resolve_local(path, root):
    target = path.resolve(strict=True)
    if not target.is_relative_to(root):
        raise ValueError("target is outside the firmware directory")
    return target


def file_identity(path):
    digest = sha256()
    size = 0
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def inventory_extension(entries, root):
    identities = {}
    payloads = {}
    skipped = {}
    for path in entries:
        try:
            target = resolve_local(path, root)
            if not target.is_file():
                raise ValueError("target is not a regular file")
            if target not in identities:
                identities[target] = file_identity(target)
        except (OSError, RuntimeError, ValueError) as error:
            skipped[path.name] = str(error) if isinstance(error, ValueError) else type(error).__name__
            continue
        size, digest = identities[target]
        payload = payloads.setdefault(
            (size, digest), {"bytes": size, "sha256": digest, "regular_names": [], "aliases": {}}
        )
        if path.is_symlink():
            payload["aliases"][path.name] = target.relative_to(root).as_posix()
        else:
            payload["regular_names"].append(path.name)
    return {
        "discovered_name_count": len(entries),
        "name_count": len(entries) - len(skipped),
        "unique_payload_count": len(payloads),
        "payloads": list(payloads.values()),
        "skipped": skipped,
    }


def inventory_revision(root, revision):
    name = f"C-4378__s-{revision}"
    try:
        directory = resolve_local(root / name, root)
        entries = sorted(directory.iterdir())
    except FileNotFoundError:
        return {"directory": name, "status": "missing"}
    except (OSError, RuntimeError, ValueError) as error:
        return {
            "directory": name,
            "status": "unavailable",
            "reason": str(error) if isinstance(error, ValueError) else type(error).__name__,
        }
    return {
        "directory": name,
        "status": "available",
        "extensions": {
            extension: inventory_extension([path for path in entries if path.suffix == extension], root)
            for extension in EXTENSIONS
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "firmware_directory",
        type=Path,
        help="Local directory containing the BCM4378 B1 or B3 firmware subdirectories",
    )
    args = parser.parse_args()
    try:
        root = args.firmware_directory.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        parser.error(f"Could not resolve firmware directory: {type(error).__name__}")
    if not root.is_dir():
        parser.error("Expected a firmware directory")
    report = {
        "revisions": {revision: inventory_revision(root, revision) for revision in REVISIONS}
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
