#!/usr/bin/env python3
"""Read the M1 Air BCM4378 inventory from macOS and installed firmware files."""

import json
from pathlib import Path
import plistlib
import re
import subprocess
import sys

from inspect_firmware import (
    BTC_PARAMETER_KEY,
    DFS_PROXY_KEY,
    MAGIC_PACKET_KEY,
    RADIO_POWER_CONFIG_KEYS,
    ROAM_CONFIG_KEYS,
    TRANSPORT_CONFIG_KEYS,
    decode_btc_parameters,
    read_artifact,
    summarize_config_keys,
)


DRIVER_BUNDLE = Path("/System/Library/DriverExtensions/com.apple.DriverKit-AppleBCMWLAN.dext")
SHARED_FIRMWARE = Path("/usr/share/firmware/wifi")
FILE_ROLES = ("Firmware", "NVRAM", "Regulatory", "TxCap")
FIRMWARE_PATH = re.compile(r"C-4378__s-[A-Z0-9]+/[A-Za-z0-9._+-]+\.(trx|txt|clmb|txcb)")
CAPABILITY_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
LINK_RATES = {1: 2.5, 2: 5, 3: 8, 4: 16, 5: 32, 6: 64}
BLUETOOTH_FIELDS = {
    "controller_chipset": "chipset",
    "controller_firmwareVersion": "firmware_version",
    "controller_transport": "transport",
    "controller_productID": "product_id",
    "controller_vendorID": "vendor_id",
    "controller_supportedServices": "reported_services",
}


def run(*args):
    return subprocess.check_output(args, timeout=20)


def registry_entries(entries):
    for entry in entries:
        yield entry
        yield from registry_entries(entry.get("IORegistryEntryChildren", []))


def pci_id(entry):
    vendor = entry.get("vendor-id", b"")
    device = entry.get("device-id", b"")
    if isinstance(vendor, bytes) and isinstance(device, bytes) and vendor and device:
        return f"{int.from_bytes(vendor, 'little'):04x}:{int.from_bytes(device, 'little'):04x}"
    return None


def link_fields(raw_value):
    if not isinstance(raw_value, int) or raw_value in (0, 0xffff):
        return None
    return {
        "raw": f"0x{raw_value:x}",
        "rate_gt_s": LINK_RATES.get(raw_value & 0xf),
        "width_lanes": (raw_value >> 4) & 0x3f,
    }


def pci_snapshot(entry):
    sizes = []
    for region in entry.get("IODeviceMemory", []):
        if isinstance(region, list):
            for description in region:
                if isinstance(description, dict) and isinstance(description.get("length"), int):
                    sizes.append(description["length"])
    power = entry.get("IOPowerManagement", {})
    return {
        "id": pci_id(entry),
        "link_status": link_fields(entry.get("IOPCIExpressLinkStatus")),
        "link_capabilities": link_fields(entry.get("IOPCIExpressLinkCapabilities")),
        "memory_aperture_lengths_bytes": sizes,
        "reported_power_states": {
            key: power[key]
            for key in ("CurrentPowerState", "DevicePowerState", "MaxPowerState")
            if isinstance(power.get(key), int)
        },
    }


def interface_status(name):
    result = subprocess.run(
        ("/sbin/ifconfig", name), capture_output=True, text=True, timeout=20
    )
    if result.returncode != 0:
        return {"flags": [], "link_status": None}
    flags = re.search(r"(?m)^[^\n]+flags=[^<\n]*<([^>\n]*)>", result.stdout)
    link = re.search(r"(?m)^\s+status:\s+(\w+)", result.stdout)
    return {
        "flags": flags.group(1).split(",") if flags else [],
        "link_status": link.group(1) if link else None,
    }


def interface_roles(entries):
    roles = []
    for entry in entries:
        if entry.get("IOObjectClass") != "IOUserNetworkWLAN":
            continue
        prefix, unit = entry.get("IOInterfaceNamePrefix"), entry.get("IOInterfaceUnit")
        if not isinstance(prefix, str) or not re.fullmatch(r"[a-z][a-z0-9]*", prefix):
            continue
        if not isinstance(unit, int) or unit < 0:
            continue
        name = f"{prefix}{unit}"
        roles.append({
            "name": name,
            "driver_class": entry.get("IOUserClass"),
            "role": entry.get("IO80211VirtualInterfaceRole", entry.get("IO80211InterfaceRole")),
            **interface_status(name),
        })
    return sorted(roles, key=lambda role: role["name"])


def compare_installed_file(bundle_path, shared_path):
    content, identity = read_artifact(bundle_path)
    shared_match = shared_path.is_file() and content == shared_path.read_bytes()
    return {"driver_bundle": identity, "matches_shared_copy": shared_match}


def requested_firmware(core):
    raw_requests = core.get("RequestedFiles")
    if not isinstance(raw_requests, list):
        return []
    requests = []
    for request in raw_requests:
        if not isinstance(request, dict):
            continue
        files = {}
        for role in FILE_ROLES:
            name = request.get(role)
            if isinstance(name, str) and FIRMWARE_PATH.fullmatch(name):
                bundle_path = DRIVER_BUNDLE / "Firmware" / name
                files[role] = {"requested_name": name}
                if bundle_path.is_file():
                    files[role].update(compare_installed_file(bundle_path, SHARED_FIRMWARE / name))
        if files:
            requests.append(files)
    return requests


def wifi_capability_inputs(core, bus):
    pcie = bus.get("WiFiCapability")
    if not isinstance(pcie, dict):
        pcie = {}
    flags = core.get("wlan.hw.feature-flags")
    raw_capabilities = core.get("FWCap")
    words = None
    if isinstance(raw_capabilities, str) and len(raw_capabilities) <= 1024:
        candidates = raw_capabilities.split()
        if all(CAPABILITY_WORD.fullmatch(word) for word in candidates):
            words = candidates
    return {
        "pcie": {key: pcie[key] for key in ("awdl", "ranging") if type(pcie.get(key)) is bool},
        "hardware_feature_flags": flags if type(flags) is int and 0 <= flags <= 0xffffffff else None,
        "firmware_capability_words": words,
    }


def reporting_legend(entries):
    reporter = next((entry for entry in entries if entry.get("IOUserClass") == "IO80211ReporterProxy"), {})
    legend = reporter.get("IOReportLegend")
    if not isinstance(legend, list):
        return None
    return reporter.get("IOReportLegendPublic") is True, legend


def report_legend_rows(legend):
    for row in legend:
        if not isinstance(row, dict):
            continue
        group = row.get("IOReportGroupName")
        subgroup = row.get("IOReportSubGroupName")
        channels = row.get("IOReportChannels")
        if not isinstance(group, str) or not isinstance(channels, list):
            continue
        labels = [
            item[2] for item in channels
            if isinstance(item, list) and len(item) > 2 and isinstance(item[2], str)
        ]
        yield group, subgroup, labels


def radio_chain_reporting(entries):
    report = reporting_legend(entries)
    if report is None:
        return None
    public, legend = report
    omi = {}
    nss_state = []
    for group, subgroup, labels in report_legend_rows(legend):
        if subgroup == "OMI Counters" and group in ("Chip", "Slice 0", "Slice 1"):
            omi[group] = labels
        if subgroup == "NSS" and re.fullmatch(r"Interface en[0-9]+", group) and "NSS State" in labels:
            nss_state.append(group.removeprefix("Interface "))
    return {
        "legend_marked_public": public,
        "omi_counter_labels": omi,
        "nss_state_interfaces": sorted(set(nss_state)),
    }


def wme_tid_reporting(entries):
    report = reporting_legend(entries)
    if report is None:
        return None
    public, legend = report
    groups = {
        f"{counter} Slice {slice_id}"
        for counter in ("Tx MPDU WME", "Rx MPDU WME", "Rx MPDU Lost")
        for slice_id in (0, 1)
    }
    return {
        "legend_marked_public": public,
        "counter_labels_by_group": {
            group: [
                label.strip() for label in labels
                if re.fullmatch(r"(?:[TR]x MPDU|Rx LOST MPDU (?:BA|NonBA)) Tid[0-7]", label.strip())
            ]
            for group, subgroup, labels in report_legend_rows(legend)
            if group in groups and subgroup == "Counters"
        },
    }


def he_ru_counter_legend(entries):
    report = reporting_legend(entries)
    if report is None:
        return None
    public, legend = report
    counter_groups = []
    for group, subgroup, labels in report_legend_rows(legend):
        ru_sizes = group in ("Chip", "Slice 0", "Slice 1") and subgroup in (
            "Tx OFDMA RU Counters", "Rx OFDMA RU Counters",
        )
        mpdus = group == "MPDUs per RU" and isinstance(subgroup, str) and re.fullmatch(
            r"Rx MPDU in AMPDU in (?:20|40|80|160) Mhz BW", subgroup,
        )
        if ru_sizes or mpdus:
            counter_groups.append({
                "group": group,
                "subgroup": subgroup,
                "labels": [
                    label.strip() for label in labels
                    if re.fullmatch(
                        r"(?:[TR]x RU size (?:26|52|106|242|484|996|2x996)|"
                        r"Rx MPDU in AMPDU in (?:26|52|106|242|484|996|2x996) Tone RU)",
                        label.strip(),
                    )
                ],
            })
    return {"legend_marked_public": public, "counter_groups": counter_groups}


def tvpm_reporting(entries):
    report = reporting_legend(entries)
    if report is None:
        return None
    public, legend = report
    fields = {
        "Tx Duty Cycle (%)", "Tx Power Backoff (1/4dBm)", "Active Chains", "Temperature (C)",
        "Battery Voltage (10xV)", "PPM", "CTLM Index", "TVPM Updates",
    }
    return {
        "legend_marked_public": public,
        "value_labels_by_slice": {
            group: [label for label in labels if label in fields]
            for group, subgroup, labels in report_legend_rows(legend)
            if group in ("TVPM Slice 0", "TVPM Slice 1") and subgroup == "Temperature Voltage Power Management"
        },
    }


def dfs_proxy_reporting(entries):
    report = reporting_legend(entries)
    if report is None:
        return None
    public, legend = report
    peer_labels = {}
    switch_reasons = {}
    infrastructure_interfaces = set()
    for group, subgroup, labels in report_legend_rows(legend):
        if subgroup == "AWDL Statistics" and re.fullmatch(r"Interface awdl[0-9]+", group):
            peer_labels[group.removeprefix("Interface ")] = [
                label for label in labels
                if label == "Cached Peers On DFS" or label.startswith("DFS Proxy Mode ")
            ]
        if subgroup == "Channel Switch Reasons" and re.fullmatch(r"Channel Switch: Slice [0-9]+", group):
            switch_reasons[group.removeprefix("Channel Switch: ")] = labels
        if subgroup == "Association Join Counters" and re.fullmatch(r"Interface en[0-9]+", group):
            if "Channel Switch Event" in labels:
                infrastructure_interfaces.add(group.removeprefix("Interface "))
    return {
        "legend_marked_public": public,
        "awdl_dfs_proxy_labels": peer_labels,
        "channel_switch_reason_labels": switch_reasons,
        "channel_switch_event_interfaces": sorted(infrastructure_interfaces),
    }


def roaming_reporting(entries):
    report = reporting_legend(entries)
    if report is None:
        return None
    public, legend = report
    association = {}
    scans = {}
    for group, subgroup, labels in report_legend_rows(legend):
        if subgroup == "Association Join Counters" and re.fullmatch(r"Interface en[0-9]+", group):
            association[group.removeprefix("Interface ")] = [
                name for name in map(str.strip, labels)
                if name == "BSSID Changed" or name.startswith("Roam ")
            ]
        if group in ("Slice 0", "Slice 1") and subgroup in ("Count Per Scan Type", "Dur   Per Scan Type"):
            scans.setdefault(group, []).extend(
                name for name in map(str.strip, labels) if "Roam" in name
            )
    return {
        "legend_marked_public": public,
        "association_labels_by_interface": association,
        "scan_labels_by_slice": scans,
    }


def aggregation_reporting(entries):
    report = reporting_legend(entries)
    if report is None:
        return None
    public, legend = report
    prefixes = {
        "Rx MPDU in SU AMPDU Usage": "Rx MPDU in SU AMPDU Usage ",
        "Tx MPDU in AMPDU Usage": "Tx MPDU in AMPDU ",
        "Rx MPDU in OFDMA AMPDU Usage": "Rx MPDU in OFDMA AMPDU Usage ",
    }
    chip_labels = []
    buckets = {}
    for group, subgroup, labels in report_legend_rows(legend):
        if group == "Chip" and subgroup == "AMPDU Counters":
            chip_labels = labels
        if group == "AMPDU" and isinstance(subgroup, str) and subgroup in prefixes:
            prefix = prefixes[subgroup]
            indexes = [label.removeprefix(prefix) for label in labels if label.startswith(prefix)]
            buckets[subgroup] = sorted(int(index) for index in indexes if re.fullmatch(r"[0-9]+", index))
    return {
        "legend_marked_public": public,
        "chip_ampdu_counter_labels": chip_labels,
        "ampdu_bucket_indexes_by_subgroup": buckets,
    }


def bluetooth_snapshot():
    report = json.loads(run("/usr/sbin/system_profiler", "SPBluetoothDataType", "-detailLevel", "basic", "-json"))
    snapshot = {}
    for block in report.get("SPBluetoothDataType", []):
        controller = block.get("controller_properties")
        if isinstance(controller, dict):
            snapshot.update({label: controller[key] for key, label in BLUETOOTH_FIELDS.items() if key in controller})
            break
    endpoints = plistlib.loads(run("/usr/sbin/ioreg", "-a", "-l", "-p", "IOService", "-r", "-n", "bluetooth-pcie", "-d", "2"))
    endpoint = next((device for device in endpoints if pci_id(device) == "14e4:5f69"), None)
    if endpoint:
        snapshot["pci_id"] = pci_id(endpoint)
        snapshot["pci_child_services"] = [
            node["IORegistryEntryName"]
            for node in endpoint.get("IORegistryEntryChildren", [])
            if isinstance(node.get("IORegistryEntryName"), str)
        ]
    return snapshot or None


def collect():
    roots = plistlib.loads(run("/usr/sbin/ioreg", "-a", "-l", "-p", "IOService", "-r", "-n", "wlan", "-d", "5", "-w", "0"))
    pci = next((entry for entry in roots if pci_id(entry) == "14e4:4425"), None)
    if pci is None:
        raise ValueError("The BCM4378 Wi-Fi PCIe device was not found in I/O Registry")
    entries = list(registry_entries([pci]))
    core = next((entry for entry in entries if entry.get("IOUserClass") == "AppleBCMWLANCore"), {})
    bus = next(
        (entry for entry in entries if entry.get("IOUserClass") == "AppleBCMWLANBusInterfacePCIe"),
        {},
    )
    route = subprocess.run(
        ("/sbin/route", "-n", "get", "default"), capture_output=True, text=True, timeout=20
    )
    default_route = re.search(r"(?m)^\s*interface:\s+(\w+)", route.stdout)
    build = run("/usr/bin/sw_vers", "-buildVersion").decode().strip()
    version = run("/usr/bin/sw_vers", "-productVersion").decode().strip()
    model = run("/usr/sbin/sysctl", "-n", "hw.model").decode().strip()

    platform = "shikoku-PlatformConfig.plist"
    platform_bundle = DRIVER_BUNDLE / "PlatformConfig" / "macOS" / platform
    coexistence_data = bus.get(BTC_PARAMETER_KEY)
    coexistence = decode_btc_parameters(coexistence_data) if isinstance(coexistence_data, bytes) else None
    ptm_mode = core.get("PTM_Mode")
    report = {
        "host": {"model": model, "macos_version": version, "macos_build": build},
        "default_ipv4_interface": default_route.group(1) if default_route else None,
        "wifi": {
            "pci": pci_snapshot(pci),
            "requested_files": requested_firmware(core),
            "running_firmware": core.get("FirmwareVersion"),
            "interface_roles": interface_roles(entries),
            "capability_inputs": wifi_capability_inputs(core, bus),
            "pcie_ptm_mode": ptm_mode if type(ptm_mode) is int else None,
            "coexistence_parameters": coexistence,
            "dfs_proxy": {
                "board_property": summarize_config_keys(bus, (DFS_PROXY_KEY,)).get(DFS_PROXY_KEY),
                "reporting": dfs_proxy_reporting(entries),
            },
            "sleep_offload_properties": {
                "magic_packet_board_property": summarize_config_keys(bus, (MAGIC_PACKET_KEY,)).get(
                    MAGIC_PACKET_KEY
                ),
                "mdns_keepalive_by_service": {
                    entry["IOUserClass"]: entry["mDNS_Keepalive"]
                    for entry in entries
                    if entry.get("IOUserClass") in (
                        "AppleBCMWLANSkywalkInterface",
                        "AppleBCMWLANLowLatencyInterface",
                    )
                    and type(entry.get("mDNS_Keepalive")) is bool
                },
            },
            "radio_power_config_properties": summarize_config_keys(bus, RADIO_POWER_CONFIG_KEYS),
            "roaming": {
                "platform_properties": summarize_config_keys(bus, ROAM_CONFIG_KEYS),
                "reporting": roaming_reporting(entries),
            },
            "radio_chain_reporting": radio_chain_reporting(entries),
            "wme_tid_reporting": wme_tid_reporting(entries),
            "he_ru_counter_legend": he_ru_counter_legend(entries),
            "aggregation_counter_legend": aggregation_reporting(entries),
            "tvpm_reporting": tvpm_reporting(entries),
            "transport_config_properties": {
                key: bus[key] for key in TRANSPORT_CONFIG_KEYS if type(bus.get(key)) is int
            },
        },
        "bluetooth": bluetooth_snapshot(),
    }
    if platform_bundle.is_file():
        report["wifi"]["platform_config"] = compare_installed_file(platform_bundle, SHARED_FIRMWARE / platform)
    return report


def main():
    try:
        report = collect()
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"Could not read the macOS inventory: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
