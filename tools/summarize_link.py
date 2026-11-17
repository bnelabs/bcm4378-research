#!/usr/bin/env python3
"""Summarize saved CoreWLAN samples as JSON without querying the interface."""

import argparse
from collections import Counter
from itertools import product
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
TRAFFIC_FIELD = "interface_traffic"
THERMAL_FIELD = "host_thermal_state"
THERMAL_STATES = ("nominal", "fair", "serious", "critical", "unknown")
COUNTER_FIELDS = ("rx_bytes", "tx_bytes", "rx_packets", "tx_packets")
MAX_UINT64 = (1 << 64) - 1
HE_DATA_TONES = {20: 234, 40: 468, 80: 980}
HE_SYMBOL_NS = 12_800
HE_GUARD_INTERVALS_NS = (800, 1600, 3200)
HE_DATA_BITS_PER_TONE = (
    (1, 2), (1, 1), (3, 2), (2, 1), (3, 1), (4, 1),
    (9, 2), (5, 1), (6, 1), (20, 3), (15, 2), (25, 3),
)


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


def read_traffic_sample(sample):
    traffic = sample.get(TRAFFIC_FIELD)
    if traffic is None:
        return "missing", None
    if not isinstance(traffic, dict):
        return "invalid", None
    interface = sample.get("interface")
    timestamp = traffic.get(TIMESTAMP)
    counters = tuple(traffic.get(field) for field in COUNTER_FIELDS)
    if interface is None or timestamp is None or None in counters:
        return "missing", None
    if type(interface) is not str or not interface:
        return "invalid", None
    if type(timestamp) not in (int, float) or not 0 <= timestamp <= MAX_UINT64:
        return "invalid", None
    if any(type(value) is not int or not 0 <= value <= MAX_UINT64 for value in counters):
        return "invalid", None
    return "complete", (interface, timestamp, counters)


def average_mbps(byte_count, seconds):
    mbps = (byte_count * 8 / 1_000_000) / seconds
    return mbps if math.isfinite(mbps) else None


def summarize_traffic(samples):
    traffic = [read_traffic_sample(sample) for sample in samples]
    intervals = dict.fromkeys(("comparable", "missing", "reset", "invalid"), 0)
    totals = Counter(dict.fromkeys(COUNTER_FIELDS, 0))
    durations = []
    for (left_status, left), (right_status, right) in zip(traffic, traffic[1:]):
        if "invalid" in (left_status, right_status):
            intervals["invalid"] += 1
            continue
        if "missing" in (left_status, right_status):
            intervals["missing"] += 1
            continue
        left_interface, left_time, left_counters = left
        right_interface, right_time, right_counters = right
        seconds = right_time - left_time
        if left_interface != right_interface or seconds <= 0:
            intervals["invalid"] += 1
            continue
        deltas = tuple(new - old for old, new in zip(left_counters, right_counters))
        if any(delta < 0 for delta in deltas):
            intervals["reset"] += 1
            continue
        intervals["comparable"] += 1
        totals.update(dict(zip(COUNTER_FIELDS, deltas)))
        durations.append(seconds)

    elapsed = math.fsum(durations) if durations else None
    return {
        "intervals": intervals,
        "observed_seconds": elapsed,
        "observed_deltas": dict(totals) if elapsed is not None else None,
        "average_mbps": {
            "rx": average_mbps(totals["rx_bytes"], elapsed),
            "tx": average_mbps(totals["tx_bytes"], elapsed),
        } if elapsed is not None else None,
    }


def nominal_he_candidates(width_mhz, reported_mbps):
    tones = HE_DATA_TONES[width_mhz]
    candidates = []
    for (mcs, (numerator, denominator)), streams, guard_ns in product(
        enumerate(HE_DATA_BITS_PER_TONE), (1, 2), HE_GUARD_INTERVALS_NS
    ):
        rate_top = tones * numerator * streams * 1000
        rate_bottom = denominator * (HE_SYMBOL_NS + guard_ns)
        if rate_top // rate_bottom == reported_mbps:
            candidates.append({
                "mcs_index": mcs,
                "spatial_streams": streams,
                "guard_interval_ns": guard_ns,
                "nominal_mbps": round(rate_top / rate_bottom, 3),
            })
    return candidates


def summarize_he_candidates(samples):
    groups = Counter()
    for sample in samples:
        rate = sample.get("tx_rate_mbps")
        width = sample.get("channel_width_mhz")
        if (
            sample.get("phy_mode") == "802.11ax"
            and width in HE_DATA_TONES
            and rate is not None
            and rate > 0
            and int(rate) == rate
        ):
            groups[width, int(rate)] += 1
    return {
        "assumptions": "Full channel, one or two streams, DCM disabled and whole-Mb/s truncation.",
        "unmodeled_samples": len(samples) - sum(groups.values()),
        "groups": [
            {
                "channel_width_mhz": width,
                "tx_rate_mbps": rate,
                "sample_count": count,
                "candidates": nominal_he_candidates(width, rate),
            }
            for (width, rate), count in sorted(groups.items())
        ],
    }


def summarize(samples, include_he_candidates=False):
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
    summary = {
        "sample_count": len(samples),
        "timestamped_samples": len(timestamps),
        "duration_seconds": duration,
        "observed_configurations": [
            {**dict(zip(LINK_FIELDS, configuration)), "sample_count": count}
            for configuration, count in configurations.items()
        ],
        "metrics": {name: summarize_metric(values) for name, values in readings.items()},
    }
    if any(sample.get(TRAFFIC_FIELD) is not None for sample in samples):
        summary[TRAFFIC_FIELD] = summarize_traffic(samples)
    thermal_states = [sample.get(THERMAL_FIELD) for sample in samples]
    if any(state is not None for state in thermal_states):
        summary["host_thermal_state_counts"] = dict(Counter(
            state if state in THERMAL_STATES else "unavailable" for state in thermal_states
        ))
    if include_he_candidates:
        summary["he_nominal_rate_candidates"] = summarize_he_candidates(samples)
    return summary


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Duration spans the earliest and latest timestamps. "
            "Adjacent readings follow input order. Power values come directly from CoreWLAN. "
            "Traffic rates cover comparable adjacent interface counter samples."
        ),
    )
    parser.add_argument(
        "input", nargs="?", default="-", help="JSON array, object, or lines. Use - for stdin."
    )
    parser.add_argument(
        "--he-candidates", action="store_true", help="Show nominal full-channel Wi-Fi 6 modes compatible with each whole-Mb/s rate."
    )
    args = parser.parse_args()
    try:
        if args.input == "-":
            text = sys.stdin.read()
        else:
            text = Path(args.input).read_text(encoding="utf-8")
        summary = summarize(read_samples(text), include_he_candidates=args.he_candidates)
        report = json.dumps(summary, indent=2, sort_keys=True, allow_nan=False)
    except (OSError, OverflowError, ValueError) as error:
        parser.error(str(error))
    print(report)


if __name__ == "__main__":
    main()
