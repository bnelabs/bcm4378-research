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
SPATIAL_REUSE_FIELDS = {
    "he_header_bss_color_known": "radiotap.he.data_1.bss_color_known",
    "he_header_bss_color": "radiotap.he.data_3.bss_color",
    "advertised_bss_color": "wlan.ext_tag.bss_color_information.bss_color",
    "advertised_bss_color_disabled": "wlan.ext_tag.bss_color_information.bss_color_disabled",
    "advertised_partial_bss_color": "wlan.ext_tag.bss_color_information.partial_bss_color",
    "advertised_psr_based_sr_support": "wlan.ext_tag.he_phy_cap.psr_based_sr_sup",
    "advertised_sr_control": "wlan.ext_tag.spatial_reuse.sr_control",
    "advertised_psr_disallowed": "wlan.ext_tag.spatial_reuse.sr_control.srp_dis",
    "advertised_non_srg_obss_pd_disallowed": "wlan.ext_tag.spatial_reuse.sr_control.non_srg_obss_pd_sr_dis",
    "advertised_non_srg_offset_present": "wlan.ext_tag.spatial_reuse.sr_control.non_srg_ofs_present",
    "advertised_srg_information_present": "wlan.ext_tag.spatial_reuse.sr_control.srg_info_present",
    "advertised_he_sig_a_reuse_15_allowed": "wlan.ext_tag.spatial_reuse.sr_control.hesiga_val_15_allowed",
    "advertised_non_srg_max_offset_db": "wlan.ext_tag.spatial_reuse.non_srg_obss_pd_max_offset",
    "advertised_srg_min_offset_db": "wlan.ext_tag.spatial_reuse.srg_obss_pd_min_offset",
    "advertised_srg_max_offset_db": "wlan.ext_tag.spatial_reuse.srg_obss_pd_max_offset",
}


def field_number(field):
    return int(field, 16) if field.lower().startswith("0x") else int(field)


def capture_field_rows(path, fields, occurrence):
    cmd = ["tshark", "-n", "-r", str(path), "-T", "fields", "-E", f"occurrence={occurrence}",
           "-E", "aggregator=,"]
    for field in fields:
        cmd.extend(("-e", field))
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, encoding="utf-8") as tshark:
        yield from csv.reader(tshark.stdout, delimiter="\t")
        if (status := tshark.wait()) != 0:
            raise subprocess.CalledProcessError(status, cmd)


def summarize_capture(path):
    records = 0
    formats = Counter()
    data_bw_or_ru = defaultdict(Counter)
    for _, raw_format, known_flag, raw_allocation in capture_field_rows(path, FIELDS, "f"):
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
    return {
        "capture_records": records,
        "records_without_radiotap_he_format": records - sum(formats.values()),
        "records_by_he_format": formats,
        "data_bandwidth_or_ru_by_he_format": data_bw_or_ru,
    }


def summarize_spatial_reuse(path):
    fields = ("frame.number", *SPATIAL_REUSE_FIELDS.values())
    records = 0
    observed = {
        name: {"records_with_field": 0, "values": Counter()} for name in SPATIAL_REUSE_FIELDS
    }
    for _, *columns in capture_field_rows(path, fields, "a"):
        if len(columns) != len(SPATIAL_REUSE_FIELDS):
            raise ValueError("unexpected TShark field count")
        records += 1
        for name, values in zip(SPATIAL_REUSE_FIELDS, columns):
            if not values:
                continue
            field = observed[name]
            field["records_with_field"] += 1
            for value in values.lower().split(","):
                key = value if value in ("true", "false") else str(field_number(value))
                field["values"][key] += 1
    return {"capture_records": records, "observed_fields": observed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Local capture file, such as PCAP or PCAPNG")
    parser.add_argument("--spatial-reuse", action="store_true",
                        help="Summarize BSS color and spatial reuse fields")
    args = parser.parse_args()
    try:
        path = args.capture.resolve(strict=True)
        if not path.is_file():
            raise ValueError("expected a regular capture file")
        summary = summarize_spatial_reuse(path) if args.spatial_reuse else summarize_capture(path)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
