#!/usr/bin/env python3
"""Read the M1 Air BCM4378 inventory from macOS and installed firmware files."""

import json
from pathlib import Path
import plistlib
import re
import subprocess
import sys

from inspect_firmware import read_artifact


DRIVER_BUNDLE = Path("/System/Library/DriverExtensions/com.apple.DriverKit-AppleBCMWLAN.dext")
SHARED_FIRMWARE = Path("/usr/share/firmware/wifi")
FILE_ROLES = ("Firmware", "NVRAM", "Regulatory", "TxCap")
FIRMWARE_PATH = re.compile(r"C-4378__s-[A-Z0-9]+/[A-Za-z0-9._+-]+\.(trx|txt|clmb|txcb)")
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
    route = subprocess.run(
        ("/sbin/route", "-n", "get", "default"), capture_output=True, text=True, timeout=20
    )
    default_route = re.search(r"(?m)^\s*interface:\s+(\w+)", route.stdout)
    build = run("/usr/bin/sw_vers", "-buildVersion").decode().strip()
    version = run("/usr/bin/sw_vers", "-productVersion").decode().strip()
    model = run("/usr/sbin/sysctl", "-n", "hw.model").decode().strip()

    platform = "shikoku-PlatformConfig.plist"
    platform_bundle = DRIVER_BUNDLE / "PlatformConfig" / "macOS" / platform
    report = {
        "host": {"model": model, "macos_version": version, "macos_build": build},
        "default_ipv4_interface": default_route.group(1) if default_route else None,
        "wifi": {
            "pci": pci_snapshot(pci),
            "requested_files": requested_firmware(core),
            "running_firmware": core.get("FirmwareVersion"),
            "interface_roles": interface_roles(entries),
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
