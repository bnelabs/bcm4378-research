#!/usr/bin/env python3
"""Summarize radiotap HE records from an existing capture using TShark."""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import subprocess


HE_FORMATS = {0: "HE_SU", 1: "HE_EXT_SU", 2: "HE_MU", 3: "HE_TRIG"}
BW_RU_CODES = {
    0: "20 MHz",
    1: "40 MHz",
    2: "80 MHz",
    3: "160 MHz or 80+80 MHz",
    4: "26-tone RU",
    5: "52-tone RU",
    6: "106-tone RU",
    7: "242-tone RU",
    8: "484-tone RU",
    9: "996-tone RU",
    10: "2x996-tone RU",
}
FIELDS = (
    "frame.number",
    "radiotap.he.data_1.ppdu_format",
    "radiotap.he.data_1.data_bw_ru_allocation_known",
    "radiotap.he.data_5.data_bw_ru_allocation",
)


def field_number(field):
    return int(field, 16) if field.lower().startswith("0x") else int(field)


def summarize_capture(path):
    cmd = ["tshark", "-n", "-r", str(path), "-T", "fields", "-E", "occurrence=f"]
    for field in FIELDS:
        cmd.extend(("-e", field))
    records = 0
    formats = Counter()
    data_bw_or_ru = defaultdict(Counter)
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, encoding="utf-8") as tshark:
        for _, raw_format, known_flag, raw_allocation in csv.reader(tshark.stdout, delimiter="\t"):
            records += 1
            if not raw_format:
                continue
            format_code = field_number(raw_format)
            format_name = HE_FORMATS.get(format_code, f"unrecognized format {format_code}")
            formats[format_name] += 1
            allocation = "unknown"
            if known_flag.lower() in ("true", "1") and raw_allocation:
                code = field_number(raw_allocation)
                allocation = BW_RU_CODES.get(code, f"reserved code {code}")
            data_bw_or_ru[format_name][allocation] += 1
        if (status := tshark.wait()) != 0:
            raise subprocess.CalledProcessError(status, cmd)
    return {
        "capture_records": records,
        "records_without_radiotap_he_format": records - sum(formats.values()),
        "records_by_he_format": formats,
        "data_bandwidth_or_ru_by_he_format": data_bw_or_ru,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Local capture file, such as PCAP or PCAPNG")
    args = parser.parse_args()
    try:
        path = args.capture.resolve(strict=True)
        if not path.is_file():
            raise ValueError("expected a regular capture file")
        summary = summarize_capture(path)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
