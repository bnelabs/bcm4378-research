#!/usr/bin/env python3
"""Summarize BCM4378 dwell and retune histograms from saved channel-switch samples."""

import argparse
from decimal import Decimal, InvalidOperation
import json
from math import isfinite
from pathlib import Path

from inspect_firmware import read_artifact


UNITS = {
    "Dwell Time": ("0x0100007c00000000", "ms", 1),
    "Phy Switch Time": ("0x0100007900000000", "us", 1000),
}


def validate_buckets(buckets, where):
    if not buckets:
        raise ValueError(f"{where} has no histogram buckets")
    previous_upper = None
    for index, row in enumerate(buckets):
        if "lower_exclusive" not in row or "upper_inclusive" not in row:
            raise ValueError(f"{where} has no bounds available at index {index}")
        lower = row["lower_exclusive"]
        upper = row["upper_inclusive"]
        if (row["index"] != index or lower != previous_upper
                or (index < len(buckets) - 1 and type(upper) is not int)
                or (index == len(buckets) - 1 and upper is not None)
                or (lower is not None and upper is not None and upper <= lower)):
            raise ValueError(f"{where} has invalid bucket bounds at index {index}")
        previous_upper = upper
        hits = row["hits"]
        if type(hits) is not int or hits < 0:
            raise ValueError(f"{where} has an invalid count at index {index}")
        if not hits:
            continue
        low, high, total = (row[name] for name in ("min", "max", "sum"))
        if (any(type(value) is not int for value in (low, high, total))
                or not 0 <= low <= high or not low * hits <= total <= high * hits
                or (lower is not None and low <= lower) or (upper is not None and high > upper)):
            raise ValueError(f"{where} has invalid observations at index {index}")


def load_sample(path):
    raw, _ = read_artifact(path)
    sample = json.loads(raw)
    stamp = sample["sampled_at_unix_seconds"]
    if type(stamp) not in (int, float) or not isfinite(stamp):
        raise ValueError(f"{path} has an invalid timestamp")
    histograms = {}
    for row in sample["reports"]:
        name = row["name"]
        if row["format"] != 3 or name not in UNITS or not row["group"].startswith("Channel Switch: Slice "):
            continue
        key = (row["group"], name)
        where = " / ".join(key)
        if key in histograms or row["unit_raw_hex"] != UNITS[name][0]:
            raise ValueError(f"Unexpected histogram identity or unit for {where}")
        buckets = row["buckets"]
        validate_buckets(buckets, where)
        histograms[key] = buckets
    if not histograms:
        raise ValueError(f"{path} has no switch timing histograms")
    return stamp, histograms


def summarize_buckets(current, prior, budget):
    positive = []
    if prior is not None and len(current) != len(prior):
        raise ValueError("Histogram bucket count changed")
    for index, row in enumerate(current):
        hits = row["hits"]
        total = row["sum"] if hits else 0
        if prior is not None:
            old = prior[index]
            if any(old[name] != row[name] for name in ("lower_exclusive", "upper_inclusive")):
                raise ValueError("Histogram bucket bounds changed")
            if old["hits"] and (hits < old["hits"] or row["min"] > old["min"] or row["max"] < old["max"]):
                raise ValueError("Histogram changed in a way that indicates a reset")
            hits -= old["hits"]
            total -= old["sum"] if old["hits"] else 0
        if hits:
            low, high = row["min"], row["max"]
            if not low * hits <= total <= high * hits:
                raise ValueError("Counter delta does not fit the final bucket")
            # The sum bounds a new sample after accounting for the other samples.
            minimum = max(low, total - (hits - 1) * high)
            maximum = min(high, total - (hits - 1) * low)
            positive.append((hits, minimum, maximum, total))
        elif total:
            raise ValueError("Histogram sum changed with no added hits")

    count = sum(row[0] for row in positive)
    total = sum(row[3] for row in positive)
    ranks = {f"p{percent}": (count * percent + 99) // 100 for percent in (50, 95, 99)}
    ranges = dict.fromkeys(ranks)
    cumulative = 0
    for hits, low, high, _ in positive:
        for label, rank in ranks.items():
            if cumulative < rank <= cumulative + hits:
                ranges[label] = [low, high]
        cumulative += hits
    result = {
        "events": count,
        "mean": total / count if count else None,
        "percentile_ranges": ranges,
    }
    if budget is not None:
        result["over_budget_count_range"] = [
            sum(hits for hits, low, _, _ in positive if low > budget),
            sum(hits for hits, _, high, _ in positive if high > budget),
        ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path, help="JSON emitted by read_wifi_airtime --channel-switch")
    parser.add_argument("--before", type=Path, help="Earlier JSON from the same running driver")
    parser.add_argument("--budget-ms", help="Bound how many records exceeded this time")
    args = parser.parse_args()
    try:
        time_budget = Decimal(args.budget_ms) if args.budget_ms is not None else None
    except InvalidOperation:
        parser.error("The time budget must be a number of milliseconds")
    try:
        if time_budget is not None and (not time_budget.is_finite() or time_budget < 0):
            raise ValueError("The time budget must be finite and nonnegative")
        stop, current = load_sample(args.sample)
        start, prior = load_sample(args.before) if args.before else (None, {})
        if start is not None and stop <= start:
            raise ValueError("The earlier sample must have a smaller timestamp")
        selected = current.keys() & prior.keys() if start is not None else current.keys()
        if not selected:
            raise ValueError("The two samples have no matching switch histograms")
        reports = []
        for group, name in sorted(selected):
            _, label, scale = UNITS[name]
            budget = time_budget * scale if time_budget is not None else None
            stats = summarize_buckets(current[group, name], prior.get((group, name)), budget)
            reports.append({"group": group, "report": name, "unit": label, **stats})
    except (OSError, ArithmeticError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps({
        "elapsed_seconds": stop - start if start is not None else None,
        "budget_ms": str(time_budget) if time_budget is not None else None,
        "unpaired_histograms": [" / ".join(key) for key in sorted(current.keys() ^ prior.keys())] if start is not None else [],
        "reports": reports,
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
