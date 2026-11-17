#!/usr/bin/env python3
"""Summarize saved CoreWLAN samples as JSON without querying the interface."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import median
import sys


LINK_FIELDS = {
    "interface": str,
    "interface_mode": str,
    "phy_mode": str,
    "band": str,
    "channel": int,
    "channel_width_mhz": int,
}
METRIC_FIELDS = {
    "rssi_dbm": "rssi_dbm",
    "noise_dbm": "noise_dbm",
    "tx_phy_rate_mbps": "tx_rate_mbps",
    "corewlan_transmit_power": "corewlan_transmit_power",
}
TIMESTAMP = "sampled_at_unix_seconds"


def read_samples(text):
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        if text.lstrip().startswith("["):
            raise
        samples = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number}. {error.msg}.") from error
    else:
        samples = document if isinstance(document, list) else [document]

    if not samples:
        raise ValueError("Input contains no samples")
    for index, sample in enumerate(samples, 1):
        if not isinstance(sample, dict):
            raise ValueError(f"Sample {index} must be a JSON object")
        for field, field_type in LINK_FIELDS.items():
            value = sample.get(field)
            if value is not None and type(value) is not field_type:
                raise ValueError(
                    f"Sample {index} field {field} must be {field_type.__name__} or null"
                )
        for field in (TIMESTAMP, *METRIC_FIELDS.values()):
            value = sample.get(field)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError(f"Sample {index} field {field} must be a finite number or null")
    return samples


def summarize_metric(readings):
    measured = [value for value in readings if value is not None]
    consecutive = [
        (left, right)
        for left, right in zip(readings, readings[1:])
        if left is not None and right is not None
    ]
    return {
        "measured_samples": len(measured),
        "unavailable_samples": len(readings) - len(measured),
        "minimum": min(measured, default=None),
        "median": median(measured) if measured else None,
        "maximum": max(measured, default=None),
        "distinct_values": len(set(measured)),
        "adjacent_measured_pairs": len(consecutive),
        "equal_adjacent_pairs": sum(left == right for left, right in consecutive),
    }


def summarize(samples):
    timestamps = [sample[TIMESTAMP] for sample in samples if sample.get(TIMESTAMP) is not None]
    duration = round(max(timestamps) - min(timestamps), 6) if len(timestamps) >= 2 else None
    configurations = Counter(
        tuple(sample.get(field) for field in LINK_FIELDS) for sample in samples
    )
    readings = {
        name: [sample.get(field) for sample in samples] for name, field in METRIC_FIELDS.items()
    }
    readings["reported_rssi_minus_noise_db"] = [
        rssi - noise if rssi is not None and noise is not None else None
        for rssi, noise in zip(readings["rssi_dbm"], readings["noise_dbm"])
    ]
    return {
        "sample_count": len(samples),
        "timestamped_samples": len(timestamps),
        "duration_seconds": duration,
        "observed_configurations": [
            {**dict(zip(LINK_FIELDS, configuration)), "sample_count": count}
            for configuration, count in configurations.items()
        ],
        "metrics": {name: summarize_metric(values) for name, values in readings.items()},
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Duration spans the earliest and latest timestamps. "
            "Adjacent readings follow input order. Power values come directly from CoreWLAN."
        ),
    )
    parser.add_argument(
        "input", nargs="?", default="-", help="JSON array, object, or lines. Use - for stdin."
    )
    args = parser.parse_args()
    try:
        if args.input == "-":
            text = sys.stdin.read()
        else:
            text = Path(args.input).read_text(encoding="utf-8")
        summary = summarize(read_samples(text))
        report = json.dumps(summary, indent=2, sort_keys=True, allow_nan=False)
    except (OSError, OverflowError, ValueError) as error:
        parser.error(str(error))
    print(report)


if __name__ == "__main__":
    main()
