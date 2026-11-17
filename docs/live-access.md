# Live register and RAM access

## What this Mac exposes today

The IPv4 default route uses `en0`, which macOS lists as Wi-Fi. The Ethernet adapters `en3` and `en4` reported inactive links. Keeping this Mac online depends on the active Apple Wi-Fi driver and the BCM4378.

I/O Registry exposes a live-access path for specific standard PCIe properties. Its `IOPCIExpressLinkStatus` value on `wlan@0` was `0x1012`. Apple's published IOPCIFamily source reads or refreshes the underlying link-status register on behalf of the registry using the system driver. This establishes access to the reported standard PCIe value. The public CoreWLAN API provides a separate driver-reported view of current PHY, channel, signal and transmit rate. [Apple IOPCIFamily implementation](https://github.com/apple-oss-distributions/IOPCIFamily/blob/main/IOPCIDevice.cpp), [CoreWLAN CWInterface](https://developer.apple.com/documentation/corewlan/cwinterface)

Two `IODeviceMemory` descriptors report **64 KiB and 8 MiB** of mapped aperture length. The upstream Linux driver uses separate mappings for registers and device memory. The aperture sizes leave actual on-chip RAM capacity and contents unmeasured. macOS also published numeric current, device and maximum power states of 2, 2 and 3 at the time of sampling. [Local inventory](../evidence/2026-11-17-macos-inventory.json), [Linux PCIe driver](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c)

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

## Supported tuning controls

| Surface | Verified scope |
| --- | --- |
| Channel selection | The native CoreWLAN SDK documents `setWLANChannel` and requires a disassociated interface. On the current uplink, the AP and driver negotiate the channel and width. The readout uses `supportedWLANChannels` and `wlanChannel`. [CoreWLAN channel command](https://developer.apple.com/documentation/corewlan/cwinterface/setwlanchannel%28_%3A%29), [CoreWLAN interface](https://developer.apple.com/documentation/corewlan/cwinterface) |
| Radio power and association | CoreWLAN documents power and association controls. Those operations can interrupt service and remain untested on the active uplink. [CoreWLAN interface](https://developer.apple.com/documentation/corewlan/cwinterface) |
| Transmit power and regulatory limits | The native SDK includes a transmit-power getter. It returned the integer `1496` throughout the station sample. The calibration of this field remains unresolved. The driver requests a country locale matrix and a separate board TxCap file. A documented application control for transmit power or regulatory policy remains unverified. [CoreWLAN transmit power](https://developer.apple.com/documentation/corewlan/cwinterface/transmitpower%28%29), [Sample](../evidence/2026-11-17-link-power-sample.json), [Firmware selection](firmware-layout.md) |
| Peer link and traffic class | Network framework supports opt-in Apple peer-to-peer Wi-Fi and app-level service classes. A public API for choosing the `llw0` driver role or forcing a specific peer radio channel remains unverified. [Apple peer-to-peer documentation](https://developer.apple.com/documentation/technotes/tn3213-moving-from-multipeer-connectivity-to-network-framework), [Network service class](https://developer.apple.com/documentation/network/nwparameters/serviceclass-swift.property) |

The SDK type-check accepted references to the power and channel getters, channel and power setters, and association and disassociation methods. The setters and association methods require runtime verification on a separate target.

The CoreWLAN link-quality delegate and subscription methods also type-checked. Apple documents the `com.apple.wifi.events` entitlement for application subscriptions. A stock terminal probe returned success from registration and cleanup and received zero callbacks over 8.01 seconds. That sample leaves event delivery unverified. The link diary uses the validated RSSI and transmit-rate getters. [Probe observation](../evidence/2026-11-17-corewlan-event-probe.json), [Apple event registration](https://developer.apple.com/documentation/corewlan/cwwificlient/startmonitoringevent%28with%3A%29), [Apple link-quality getters](https://developer.apple.com/documentation/corewlan/cweventdelegate/linkqualitydidchangeforwifiinterface%28withname%3Arssi%3Atransmitrate%3A%29)

Apple describes the transmit-power getter in mW and uses zero for an error. Taken literally, `1496` would be 1.496 W. The A2337 grant reports a conducted test value of 0.023 W at the associated 80 MHz group's 5,210 MHz center. The source, measurement conditions and scaling of the getter are unverified. The sampler preserves the integer under `corewlan_transmit_power`. A calibrated bench comparison would need known channel width and measurement conditions, with both the getter and instrument measurements captured at the same time. [Apple getter documentation](https://developer.apple.com/documentation/corewlan/cwinterface/transmitpower%28%29), [A2337 grant](https://fccid.io/BCGA2337#grants)

The installed CoreWLAN shared-cache image exposes the public `transmitPower` wrapper to static inspection. After two calls the wrapper converts the returned double to a signed 64-bit integer, rounded toward zero. This establishes the final conversion applied to the value returned by the public API. The source and scale of the double remain unresolved. [Sanitized wrapper evidence](../evidence/2026-11-17-corewlan-power-wrapper.json), [Apple dyld inspection tool](https://github.com/apple-oss-distributions/dyld/blob/main/other-tools/dyld_info.cpp), [Arm instruction reference, section D4.20](https://documentation-service.arm.com/static/6245c734b059dc5ff9a8bdab#page=1053)

## Separate test target

A second A2337 with an independent Ethernet or console management link is the usable setup for studying driver-owned raw access without putting this Mac's internet connection at risk. Asahi documents working Wi-Fi on the 2020 M1 MacBook Air. The upstream driver establishes a route to device memory and registers on that platform. The lab's firmware build, the impact of a diagnostic snapshot and the scope of captured state would still need verification on that target. [Asahi M1 device support](https://asahilinux.org/docs/platform/feature-support/m1/#m1-devices)
