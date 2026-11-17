#!/usr/bin/env python3
"""Summarize saved macOS power logs and decode retained WLAN keepalive status."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
from statistics import median
from struct import Struct
import sys

from inspect_firmware import read_artifact


POWER_ROW = re.compile(
    r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4})\s+"
    r"(DarkWake|WakeDetails|Sleep|Wake)(?: *\t| {2,})(.*)$"
)
DRIVER_CLAIM = re.compile(
    r"DriverReason:\s*(.*?)\s+-\s+DriverDetails:\s*(.*?)(?=DriverReason:|$)"
)
WIFI_BT = re.compile(r"\bdue to\b\s*:?\s*.*?\bwifibt\b", re.IGNORECASE)
POWER_SOURCE = re.compile(r"\bUsing (AC|BATT|Battery)\b", re.IGNORECASE)
POWER_LABELS = {"ac": "ac", "batt": "battery", "battery": "battery"}
DURATION = re.compile(r"\b(\d+) secs\s*$")
KEEPALIVE_FLAG = re.compile(r"\bTCPKeepAlive=(active|inactive)\b")
STATUS_HEADER = Struct("<HH")
TCP_STATUS = {
    0: ("Normal", None),
    1: ("No reply to keepalive", 27),
    2: ("TCP acknowledgement flag clear", 28),
    3: ("Unexpected TCP flag", 30),
    4: ("Invalid TCP acknowledgement number", 29),
    5: ("Invalid TCP sequence number", 31),
    6: ("Incoming TCP data", 26),
    255: ("Unavailable", None),
}


def power_rows(lines):
    claims_at = None
    for line in lines:
        row = POWER_ROW.match(line)
        if row:
            timestamp, domain, message = row.groups()
            stamp = int(datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S %z").timestamp())
            claims_at = stamp if domain == "WakeDetails" else None
            yield stamp, domain, message
        elif claims_at is not None and line.lstrip().startswith("DriverReason:"):
            yield claims_at, "WakeDetails", line
        else:
            claims_at = None


def summarize_rows(rows):
    events = Counter()
    sleep_flags = Counter()
    claims = defaultdict(list)
    radio_wakes = []
    for stamp, domain, message in rows:
        if domain == "WakeDetails":
            claims[stamp].extend(
                (reason.startswith("smc.sysState.Wake("), bool(detail.strip()))
                for reason, detail in DRIVER_CLAIM.findall(message)
            )
            continue
        events[domain] += 1
        if domain == "Sleep":
            flag = KEEPALIVE_FLAG.search(message)
            sleep_flags[flag[1] if flag else "unreported"] += 1
        if domain == "DarkWake" and WIFI_BT.search(message):
            source = POWER_SOURCE.search(message)
            power = POWER_LABELS[source[1].lower()] if source else "unreported"
            duration = DURATION.search(message)
            radio_wakes.append((stamp, power, int(duration[1]) if duration else None))

    by_power = {}
    for label in ("ac", "battery", "unreported"):
        durations = [duration for _, power, duration in radio_wakes if power == label]
        reported = [seconds for seconds in durations if seconds is not None]
        by_power[label] = {
            "records": len(durations),
            "records_with_duration": len(reported),
            "reported_duration_seconds_total": sum(reported),
            "reported_duration_seconds_median": median(reported) if reported else None,
        }
    return {
        "events": {domain: events[domain] for domain in ("Sleep", "DarkWake", "Wake")},
        "sleep_records_by_tcpkeepalive_flag": dict(sleep_flags),
        "wifibt_darkwakes": {
            "records": len(radio_wakes),
            "by_power_source": by_power,
            "with_driver_claim_at_same_second": sum(bool(claims[stamp]) for stamp, _, _ in radio_wakes),
            "with_smc_claim_at_same_second": sum(any(smc for smc, _ in claims[stamp]) for stamp, _, _ in radio_wakes),
            "with_nonempty_driver_details_at_same_second": sum(
                any(detail for _, detail in claims[stamp]) for stamp, _, _ in radio_wakes
            ),
        },
    }


def summarize_power_log(lines, boot_epoch):
    rows = list(power_rows(lines))
    result = {"retained": summarize_rows(rows)}
    if boot_epoch is not None:
        result["at_or_after_boot_epoch"] = summarize_rows(row for row in rows if row[0] >= boot_epoch)
    return result


def decode_tcp_status(data):
    if len(data) < STATUS_HEADER.size + 1:
        raise ValueError("Truncated TCP keepalive status record")
    command, length = STATUS_HEADER.unpack_from(data)
    if command != 4 or not 1 <= length <= len(data) - STATUS_HEADER.size:
        raise ValueError("Invalid TCP keepalive status command or length")
    count = data[STATUS_HEADER.size]
    if count >= length:
        raise ValueError("TCP keepalive status count exceeds its payload")
    slots = []
    for slot, code in enumerate(data[STATUS_HEADER.size + 1:STATUS_HEADER.size + 1 + count]):
        label, reason = TCP_STATUS.get(code, ("Unknown", None))
        slots.append({"slot": slot, "raw_status": code, "label": label, "mapped_wake_reason": reason})
    return {"reported_slot_count": count, "slots": slots}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pmset-log", help="Saved pmset -g log text, or - for standard input")
    parser.add_argument("--boot-epoch", type=int, help="Boot time in Unix seconds for the source of the power log")
    parser.add_argument("--tko-status", type=Path, help="Saved binary TKO status data property from the WLAN driver")
    args = parser.parse_args()
    if not (args.pmset_log or args.tko_status):
        parser.error("Provide --pmset-log, --tko-status, or both")
    if args.boot_epoch is not None and not args.pmset_log:
        parser.error("--boot-epoch requires --pmset-log")

    result = {}
    try:
        if args.pmset_log == "-":
            result["power_log"] = summarize_power_log(sys.stdin, args.boot_epoch)
        elif args.pmset_log:
            with Path(args.pmset_log).open(encoding="utf-8", errors="replace") as stream:
                result["power_log"] = summarize_power_log(stream, args.boot_epoch)
        if args.tko_status:
            data, _ = read_artifact(args.tko_status)
            result["tko_status"] = decode_tcp_status(data)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
