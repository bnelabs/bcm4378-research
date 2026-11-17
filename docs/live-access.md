# Live register and RAM access

## What this Mac exposes today

The IPv4 default route uses `en0`, which macOS lists as Wi-Fi. The Ethernet adapters `en3` and `en4` reported inactive links. Keeping this Mac online depends on the active Apple Wi-Fi driver and the BCM4378.

I/O Registry exposes a live-access path for specific standard PCIe properties. Its `IOPCIExpressLinkStatus` value on `wlan@0` was `0x1012`. Apple's published IOPCIFamily source reads or refreshes the underlying link-status register on behalf of the registry using the system driver. This establishes access to the reported standard PCIe value. The public CoreWLAN API provides a separate driver-reported view of current PHY, channel, signal and transmit rate. [Apple IOPCIFamily implementation](https://github.com/apple-oss-distributions/IOPCIFamily/blob/main/IOPCIDevice.cpp), [CoreWLAN CWInterface](https://developer.apple.com/documentation/corewlan/cwinterface)

These queries reproduce the host view using system commands.

```sh
route -n get default | awk '$1 == "interface:" {print $2}'
ioreg -p IOService -r -n wlan -d 1 -w 0 |
  rg 'wlan@|IOPCIExpressLinkStatus|IOPCIExpressLinkCapabilities|compatible'
ioreg -p IOService -r -n AppleBCMWLANCore -d 1 -w 0 |
  rg '^\s+"FirmwareVersion"'
swift tools/read_wifi_status.swift
```

## Device registers and firmware RAM

| Access path | Finding |
| --- | --- |
| Stock macOS support surfaces | CoreWLAN and I/O Registry expose telemetry. Wireless Diagnostics produces a support archive. The public interfaces reviewed provide no documented access to arbitrary BCM4378 registers or RAM. [CoreWLAN](https://developer.apple.com/documentation/corewlan/cwinterface), [Wireless Diagnostics](https://support.apple.com/guide/mac-help/mchlf4de377f/mac) |
| PCIDriverKit | A matched, entitled PCI driver can use PCI configuration and device-memory APIs. Apple's public documentation gives no supported way to share the internal endpoint with the existing Apple BCM4378 driver for arbitrary reads. [PCIDriverKit](https://developer.apple.com/documentation/pcidriverkit), [DriverKit entitlements](https://developer.apple.com/documentation/driverkit/requesting-entitlements-for-driverkit-development) |
| Linux `brcmfmac` | The upstream driver matches the BCM4378, maps register and device-memory regions and includes an internal RAM-copy operation for diagnostics. Some core reads use a shared window selector, so out-of-band access could interfere with the driver even when the intended operation only reads data. [Linux PCIe driver](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c), [Linux diagnostic core](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmfmac/core.c) |

## Separate test target

A second A2337 with an independent Ethernet or console management link is the usable setup for studying driver-owned raw access without putting this Mac's internet connection at risk. Asahi documents working Wi-Fi on the 2020 M1 MacBook Air. The upstream driver establishes a route to device memory and registers on that platform. The lab's firmware build, the impact of a diagnostic snapshot and the scope of captured state would still need verification on that target. [Asahi M1 device support](https://asahilinux.org/docs/platform/feature-support/m1/#m1-devices)
