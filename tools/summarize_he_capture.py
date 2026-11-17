#!/usr/bin/env python3
"""Summarize Wi-Fi PHY and capability fields from a saved capture using TShark."""

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
BEAMFORMING_FIELDS = {
    "vht_su_beamformer": "wlan.vht.capabilities.subeamformer",
    "vht_su_beamformee": "wlan.vht.capabilities.subeamformee",
    "vht_mu_beamformer": "wlan.vht.capabilities.mubeamformer",
    "vht_mu_beamformee": "wlan.vht.capabilities.mubeamformee",
    "vht_beamformee_sts_code": "wlan.vht.capabilities.beamformee_sts_cap",
    "he_su_beamformer": "wlan.ext_tag.he_phy_cap.su_beamformer",
    "he_su_beamformee": "wlan.ext_tag.he_phy_cap.su_beamformee",
    "he_mu_beamformer": "wlan.ext_tag.he_phy_cap.mu_beamformer",
    "he_beamformee_sts_lte_80mhz_code": "wlan.ext_tag.he_phy_cap.beamformee_sts_lte_80mhz",
    "he_beamformee_sts_gt_80mhz_code": "wlan.ext_tag.he_phy_cap.beamformee_sts_gt_80mhz",
    "he_triggered_su_feedback": "wlan.ext_tag.he_phy_cap.trig_su_bf_fb",
    "he_triggered_mu_partial_bandwidth_feedback": "wlan.ext_tag.he_phy_cap.trig_mu_bf_fb",
    "ndp_announcement_variant_code": "wlan.ndp.token.variant",
    "he_trigger_type_code": "wlan.trigger.he.trigger_type",
    "vht_feedback_nc_index": "wlan.vht.mimo_control.ncindex",
    "vht_feedback_nr_index": "wlan.vht.mimo_control.nrindex",
    "vht_feedback_bandwidth_code": "wlan.vht.mimo_control.chanwidth",
    "vht_feedback_grouping_code": "wlan.vht.mimo_control.grouping",
    "vht_feedback_type_code": "wlan.vht.mimo_control.feedbacktype",
    "he_feedback_nc_index": "wlan.he.mimo.nc_index",
    "he_feedback_nr_index": "wlan.he.mimo.nr_index",
    "he_feedback_bandwidth_code": "wlan.he.mimo.bw",
    "he_feedback_grouping_code": "wlan.he.mimo.grouping",
    "he_feedback_type_code": "wlan.he.mimo.feedback_type",
    "vht_phy_beamformed_known": "radiotap.vht.have_beamformed",
    "vht_phy_beamformed": "radiotap.vht.beamformed",
    "he_phy_txbf_known": "radiotap.he.data_2.txbf_known",
    "he_phy_txbf": "radiotap.he.txbf",
}
AGGREGATION_FIELDS = (
    "frame.number",
    "frame.section_number",
    "frame.interface_id",
    "radiotap.channel.freq",
    "radiotap.xchannel.freq",
    "radiotap.ampdu.reference",
    "radiotap.ampdu.flags.report_zerolen",
    "radiotap.ampdu.flags.is_zerolen",
    "radiotap.ampdu.flags.lastknown",
    "radiotap.ampdu.flags.last",
    "wlan.fc.type",
    "wlan.fc.type_subtype",
    "wlan.fc.retry",
    "wlan.qos.amsdupresent",
)


def field_number(field):
    return int(field, 16) if field.lower().startswith("0x") else int(field)


def flag_is_set(field):
    return field.lower() in ("true", "1")


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
        if flag_is_set(known_flag) and raw_allocation:
            code = field_number(raw_allocation)
            allocation = BW_RU_CODES.get(code, f"reserved code {code}")
        data_bw_or_ru[format_name][allocation] += 1
    return {
        "capture_records": records,
        "records_without_radiotap_he_format": records - sum(formats.values()),
        "records_by_he_format": formats,
        "data_bandwidth_or_ru_by_he_format": data_bw_or_ru,
    }


def summarize_metadata(path, field_names):
    fields = ("frame.number", *field_names.values())
    records = 0
    observed = {
        name: {"records_with_field": 0, "values": Counter()} for name in field_names
    }
    for _, *columns in capture_field_rows(path, fields, "a"):
        if len(columns) != len(field_names):
            raise ValueError("unexpected TShark field count")
        records += 1
        for name, values in zip(field_names, columns):
            if not values:
                continue
            field = observed[name]
            field["records_with_field"] += 1
            for value in values.lower().split(","):
                key = value if value in ("true", "false") else str(field_number(value))
                field["values"][key] += 1
    return {"capture_records": records, "observed_fields": observed}


def summarize_aggregation(path):
    records = tagged = zero_length = 0
    active_runs = {}
    last_marked = Counter()
    last_unmarked = Counter()
    data = {"decoded_records": 0, "retry_bit_set": 0, "amsdu_present": 0}
    block_ack = {"request_records": 0, "ack_records": 0}
    for row in capture_field_rows(path, AGGREGATION_FIELDS, "f"):
        (_, section, interface, frequency, extended_frequency, reference, reports_zero_length,
         raw_zero_length, last_known,
         last, frame_type, subtype, retry, amsdu) = row
        records += 1
        is_zero_length = flag_is_set(reports_zero_length) and flag_is_set(raw_zero_length)
        if not is_zero_length and frame_type and field_number(frame_type) == 2:
            data["decoded_records"] += 1
            data["retry_bit_set"] += flag_is_set(retry)
            data["amsdu_present"] += flag_is_set(amsdu)
        if not is_zero_length and subtype:
            code = field_number(subtype)
            if code == 0x18:
                block_ack["request_records"] += 1
            if code == 0x19:
                block_ack["ack_records"] += 1

        channel = frequency or extended_frequency
        stream = (section, interface, field_number(channel) if channel else None)
        previous_reference, mpdus = active_runs.get(stream, ("", 0))
        if previous_reference and reference != previous_reference:
            last_unmarked[mpdus] += 1
            del active_runs[stream]
            mpdus = 0
        if not reference:
            continue

        tagged += 1
        zero_length += is_zero_length
        mpdus += bool(subtype) and not is_zero_length
        if flag_is_set(last_known) and flag_is_set(last):
            last_marked[mpdus] += 1
            active_runs.pop(stream, None)
        else:
            active_runs[stream] = (reference, mpdus)

    last_unmarked.update(mpdus for _, mpdus in active_runs.values())
    return {
        "capture_records": records,
        "ampdu": {
            "tagged_records": tagged,
            "zero_length_records": zero_length,
            "observed_mpdus_per_run_with_last_marker": last_marked,
            "observed_mpdus_per_run_without_last_marker": last_unmarked,
        },
        "data": data,
        "block_ack": block_ack,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Local capture file, such as PCAP or PCAPNG")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--spatial-reuse", dest="metadata_fields", action="store_const",
                       const=SPATIAL_REUSE_FIELDS, help="Summarize BSS color and spatial reuse fields")
    modes.add_argument("--beamforming", dest="metadata_fields", action="store_const",
                       const=BEAMFORMING_FIELDS, help="Summarize beamforming roles, sounding, and feedback")
    modes.add_argument("--aggregation", action="store_true",
                       help="Summarize aggregate references, retries, and Block Ack")
    args = parser.parse_args()
    try:
        path = args.capture.resolve(strict=True)
        if not path.is_file():
            raise ValueError("expected a regular capture file")
        if args.aggregation:
            summary = summarize_aggregation(path)
        elif args.metadata_fields is not None:
            summary = summarize_metadata(path, args.metadata_fields)
        else:
            summary = summarize_capture(path)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
