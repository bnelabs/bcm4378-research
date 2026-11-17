#!/usr/bin/env python3
"""Measure host interface counter activity for the BCM4378 macOS Wi-Fi roles."""

import argparse
import json
import math
import re
import subprocess
import time

from summarize_link import MAX_UINT64, TIMESTAMP, TRAFFIC_FIELD, summarize_traffic


INTERFACES = ("en0", "awdl0", "llw0", "nan0", "ap1")
COLUMNS = {"Ibytes": "rx_bytes", "Obytes": "tx_bytes", "Ipkts": "rx_packets", "Opkts": "tx_packets"}


def parse_link_rows(text):
    lines = text.splitlines()
    if not lines:
        raise ValueError("netstat returned no interface rows")
    positions = {name: index for index, name in enumerate(lines[0].split())}
    if not COLUMNS.keys() <= positions.keys():
        raise ValueError("netstat returned unexpected counter columns")

    result = {}
    for line in lines[1:]:
        fields = line.split()
        if len(fields) < 3 or not fields[2].startswith("<Link#"):
            continue
        name = fields[0].rstrip("*")
        if name not in INTERFACES or max(positions[column] for column in COLUMNS) >= len(fields):
            continue
        values = {key: fields[positions[column]] for column, key in COLUMNS.items()}
        if all(value.isascii() and value.isdecimal() and int(value) <= MAX_UINT64 for value in values.values()):
            if name in result:
                raise ValueError(f"netstat returned multiple link-layer rows for {name}")
            result[name] = {key: int(value) for key, value in values.items()}
    return result


def default_interface():
    output = subprocess.check_output(
        ["/sbin/route", "-n", "get", "default"], text=True, timeout=5
    )
    match = re.search(r"^\s*interface:\s+(\w+)", output, re.MULTILINE)
    return match.group(1) if match is not None else None


def summarize_roles(samples):
    activity = {name: set() for name in INTERFACES}
    report = {}
    for name in INTERFACES:
        initial = samples[0][1].get(name)
        measurements = [
            {TIMESTAMP: timestamp, **values[name]} if name in values else None
            for timestamp, values in samples
        ]
        for index, (left, right) in enumerate(zip(measurements, measurements[1:])):
            if left is None or right is None or right[TIMESTAMP] <= left[TIMESTAMP]:
                continue
            changes = [right[key] - left[key] for key in COLUMNS.values()]
            if min(changes) >= 0 and any(changes):
                activity[name].add(index)
        report[name] = {
            "initial_counter_nonzero": any(initial.values()) if initial is not None else None,
            "link_layer_row_samples": sum(value is not None for value in measurements),
            "positive_delta_intervals": len(activity[name]),
            **summarize_traffic([
                {"interface": name, TRAFFIC_FIELD: value} for value in measurements
            ]),
        }
    for name in INTERFACES[1:]:
        report[name]["same_interval_as_en0_activity"] = len(activity["en0"] & activity[name])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=46, help="Number of snapshots, at least two")
    parser.add_argument("--interval", type=float, default=1, help="Seconds between snapshots")
    args = parser.parse_args()
    if args.samples < 2 or not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("provide at least two samples and a positive finite interval")
    try:
        before = default_interface()
        samples = []
        start = time.monotonic()
        for index in range(args.samples):
            time.sleep(max(0, start + index * args.interval - time.monotonic()))
            output = subprocess.check_output(["/usr/sbin/netstat", "-ibn"], text=True, timeout=5)
            samples.append((time.time(), parse_link_rows(output)))
        after = default_interface()
        result = {
            "default_interface_before": before,
            "default_interface_after": after,
            "elapsed_seconds": round(samples[-1][0] - samples[0][0], 6),
            "snapshot_count": len(samples),
            "interfaces": summarize_roles(samples),
        }
    except (OSError, OverflowError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
