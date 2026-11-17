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

### WLAN serial metadata

Both I/O Registry planes place `wlan-debug` under the M1's UART2. The IOService provider is `AppleSamsungSerial`, with an `AppleSimpleUARTSync` service and a serial client that publishes the callout and dial-in device names. The Wi-Fi driver attaches through a separate PCIe branch. This identifies the host serial provider and the WLAN label. Board wiring, the endpoint device and any firmware data delivered over it remain unverified. [Registry snapshot](../evidence/2026-11-17-wlan-serial-registry.json), [Apple I/O Registry planes](https://developer.apple.com/library/archive/documentation/DeviceDrivers/Conceptual/IOKitFundamentals/TheRegistry/TheRegistry.html), [Apple serial client source](https://github.com/apple-oss-distributions/IOSerialFamily/blob/IOSerialFamily-93.200.2/IOSerialFamily.kmodproj/IOSerialBSDClient.cpp#L610-L725)

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
| Transmit power and regulatory limits | The public getter reports a milliwatt value. The driver conversion and repeatable readout support the interpretation below. Country locale matrix and board TxCap files are separate driver inputs. A documented macOS application control for transmit power remains unverified. [CoreWLAN transmit power](https://developer.apple.com/documentation/corewlan/cwinterface/transmitpower%28%29), [Driver conversion evidence](../evidence/2026-11-17-txpower-provenance.json), [Firmware selection](firmware-layout.md) |
| Peer link and traffic class | Network framework supports opt-in Apple peer-to-peer Wi-Fi and app-level service classes. A public API for choosing the `llw0` driver role or forcing a specific peer radio channel remains unverified. [Apple peer-to-peer documentation](https://developer.apple.com/documentation/technotes/tn3213-moving-from-multipeer-connectivity-to-network-framework), [Network service class](https://developer.apple.com/documentation/network/nwparameters/serviceclass-swift.property) |

The SDK type-check accepted references to the power and channel getters, channel and power setters, and association and disassociation methods. The setters and association methods require runtime verification on a separate target.

The CoreWLAN link-quality delegate and subscription methods also type-checked. Apple documents the `com.apple.wifi.events` entitlement for application subscriptions. A stock terminal probe returned success from registration and cleanup and received zero callbacks over 8.01 seconds. That sample leaves event delivery unverified. The link diary uses the validated RSSI and transmit-rate getters. [Probe observation](../evidence/2026-11-17-corewlan-event-probe.json), [Apple event registration](https://developer.apple.com/documentation/corewlan/cwwificlient/startmonitoringevent%28with%3A%29), [Apple link-quality getters](https://developer.apple.com/documentation/corewlan/cweventdelegate/linkqualitydidchangeforwifiinterface%28withname%3Arssi%3Atransmitrate%3A%29)

### Station diagnostic fields

The installed CoreWLAN headers expose current PHY mode, channel, transmit rate, RSSI and noise. The installed `wdutil info` path requires root and uses a formatter with fields for MCS index, spatial streams, guard interval and clear channel assessment (CCA). Its formatter labels CCA as a percentage and gives no guard-interval unit. The installed driver has a separate guard-interval getter that decodes a firmware rate specification. [Diagnostic format and access evidence](../evidence/2026-11-17-station-diagnostic-surfaces.json), [Driver rate evidence](../evidence/2026-11-17-tx-rate-provenance.json), [Apple CoreWLAN](https://developer.apple.com/documentation/corewlan/cwinterface)

The System Profiler Wi-Fi reporter has a current-network MCS field. Its standard path can initiate a Wi-Fi scan. The compact CLI mode dispatches multiple hardware and network reporters. Live MCS, stream count, guard interval and CCA on this station remain unmeasured. [Static reporter evidence](../evidence/2026-11-17-station-diagnostic-surfaces.json)

### Transmit-power readout

Static inspection found that the installed Apple driver's transmit-power getter reads the first byte of the firmware's `qtxpower` result and converts quarter-dBm to milliwatts. All 40 lookup entries match Broadcom's published table in both installed driver slices. The public CoreWLAN wrapper dispatches to CoreWiFi and truncates the returned double to an integer. The CoreWiFi client reads the XPC reply as a double. Its Apple80211 handler boxes the integer from a driver reply. Static inspection establishes these conversions and leaves the runtime server dispatch unobserved. [Driver and framework evidence](../evidence/2026-11-17-txpower-provenance.json), [Apple getter documentation](https://developer.apple.com/documentation/corewlan/cwinterface/transmitpower%28%29), [Broadcom conversion source](https://android.googlesource.com/platform/hardware/broadcom/wlan/+/b5876d709a5573570d2ee218a3fabce6fc18d0db/bcmdhd/dhdutil/bcmutils.c)

Of the 256 possible byte inputs, only 127 maps to 1,496 mW through that conversion. Linux `brcmfmac` uses 127 quarter-dBm in its automatic power request. Six fresh CoreWLAN polls on channel 40 at 80 MHz each returned `1496`, matching the earlier sample. The readout is consistent with the converted automatic power setting. The live firmware byte and macOS policy flag remain unverified. [Sample and conversion check](../evidence/2026-11-17-txpower-provenance.json), [Linux automatic power request](https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L2659-L2710)

The link diary preserves the raw API integer under `corewlan_transmit_power`. For physical power, record the same getter alongside a calibrated RF instrument with band, width, geometry and workload held fixed on the separate test setup. The A2337's grant lists a 0.023 W conducted test result at the 5,210 MHz center of this 80 MHz group. [A2337 grant](https://fccid.io/BCGA2337#grants)

## Separate test target

A second A2337 with an independent Ethernet or console management link is the usable setup for studying driver-owned raw access without putting this Mac's internet connection at risk. Asahi documents working Wi-Fi on the 2020 M1 MacBook Air. The upstream driver establishes a route to device memory and registers on that platform. The lab's firmware build, the impact of a diagnostic snapshot and the scope of captured state would still need verification on that target. [Asahi M1 device support](https://asahilinux.org/docs/platform/feature-support/m1/#m1-devices)

The versioned Linux and Asahi sources identify standard station telemetry, channel reporting and power policy paths for the bench. The Asahi build can report HE rate details when firmware supplies them. Its generic advertised capabilities and the actual station or RF measurements carry different evidence. [Driver comparison and bench checks](asahi-controls.md)
