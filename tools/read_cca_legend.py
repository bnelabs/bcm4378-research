#!/usr/bin/env python3
"""Inventory the current BCM4378 CCA reporter labels without sampling values."""

import argparse
import json
import plistlib
import re
import subprocess

from read_macos_inventory import registry_entries, run


CHANNEL_REPORTS = {
    "CCA Last Reported": "cca_last_reported",
    "CCA State": "cca_state",
    "Noise Last Reported": "noise_last_reported",
    "Noise State": "noise_state",
}
INTERFACES = {"Interface en0": "en0", "Interface awdl0": "awdl0"}
INTERFACE_REPORTS = {
    "Average CCA", "Average CCA State", "IBSS CCA", "IBSS CCA State",
    "OBSS CCA", "OBSS CCA State", "Interference CCA", "Interference CCA State",
    "Noise Floor", "Noise Floor State", "QBSS Values", "QBSS Channel Utilitzation",
}
CHANNEL_NAME = re.compile(r"Channel (?:CCA|Noise)(?: State)?\s+(\d+)")


def inventory(entries):
    reporters = [entry for entry in entries if entry.get("IOUserClass") == "IO80211ReporterProxy"]
    if len(reporters) != 1:
        raise ValueError(f"Expected one WLAN reporter proxy, found {len(reporters)}")
    reporter = reporters[0]
    legend = reporter.get("IOReportLegend")
    if not isinstance(legend, list):
        raise ValueError("The reporter has no legend array")

    channel_numbers = {label: [] for label in CHANNEL_REPORTS.values()}
    subgroups = {name: set() for name in INTERFACES.values()}
    excluding_own = 0
    channel_entries = 0
    qbss_utilization_present = False
    for row in legend:
        if not isinstance(row, dict):
            continue
        group = row.get("IOReportGroupName", "")
        subgroup = row.get("IOReportSubGroupName")
        channels = row.get("IOReportChannels")
        if not isinstance(channels, list) or not isinstance(group, str) or not isinstance(subgroup, str):
            continue
        channel_entries += len(channels)
        names = [item[2] for item in channels if isinstance(item, list) and len(item) > 2
                 and isinstance(item[2], str)]
        if group == "Channel" and subgroup in CHANNEL_REPORTS:
            for name in names:
                match = CHANNEL_NAME.fullmatch(name)
                if match:
                    channel_numbers[CHANNEL_REPORTS[subgroup]].append(int(match.group(1)))
        if group in INTERFACES and subgroup in INTERFACE_REPORTS:
            subgroups[INTERFACES[group]].add(subgroup)
        if group == "Interface en0" and subgroup == "QBSS Values":
            qbss_utilization_present |= "Channel Utilization" in names
        if group.startswith("Interface en0 Peer ") and subgroup == "Link quality monitor measurements":
            excluding_own += names.count("CCA (%) excluding own traffic")

    return {
        "legend_marked_public": reporter.get("IOReportLegendPublic") is True,
        "legend_rows": len(legend),
        "legend_channel_entries": channel_entries,
        "channel_number_labels": {name: sorted(values) for name, values in channel_numbers.items()},
        "interface_subgroups": {name: sorted(values) for name, values in subgroups.items()},
        "link_quality_excluding_own_traffic_labels": excluding_own,
        "en0_qbss_channel_utilization_label": qbss_utilization_present,
        "scope": "Published I/O Registry metadata only",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        raw = run("/usr/sbin/ioreg", "-a", "-l", "-p", "IOService", "-r", "-n", "wlan", "-d", "6")
        result = inventory(registry_entries(plistlib.loads(raw)))
    except (OSError, ValueError, subprocess.SubprocessError, plistlib.InvalidFileException) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
