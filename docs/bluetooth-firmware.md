# BCM4378 Bluetooth companion firmware

## Running controller

System Information reports `BCM_4378` firmware version `24.2.551.4122` over PCIe. I/O Registry reports endpoint `14e4:5f69`, PCI revision ID 3, a 5.0 GT/s ×1 link and two mapped aperture lengths of 32 KiB and 4 MiB. These are host-reported ranges. Controller RAM contents and capacity remain unmeasured. The AppleConvergedPCI and AppleConvergedIPCOLYBTControl kernel extensions were listed as loaded. The latter's on-disk personalities include log and core-dump providers. Their runtime availability through a supported interface remains open. [Host evidence](../evidence/2026-11-17-bluetooth-host.json), [Linux BCM4378 Bluetooth identifier](https://github.com/torvalds/linux/blob/v6.12/drivers/bluetooth/hci_bcm4377.c)

The running version matches one installed image, `BCM4378B1_24.2.551.4122_PCIE_macOS_Shikoku_OS_MUR_20260715.bin`. Its embedded identity independently agrees with the version, board and vendor in its filename. The catalog pairs it with `BCM4378B1_FinalV0_PCIE_macOS_Shikoku_OS_MUR_K_R_20200902.ptb`. A 12-second-bounded search of the previous 24 hours of unified logs timed out. Direct evidence of the runtime paths and a live byte comparison remain unavailable. [Host observation](../evidence/2026-11-17-bluetooth-host.json), [Catalog](../evidence/2026-11-17-bluetooth-catalog.json)

## Catalog and layout

The installed directory contains 11 distinct BCM4378 binaries and 11 PTB names resolving to five distinct payloads. B1 has MUR and USI variants for AtlantisB, Capri, Honshu, Santorini and Shikoku. B3 has Kyushu USI. The two Shikoku PTB names resolve to the same 520-byte file. The Kyushu B3 and Honshu B1 PTB names also resolve to the same file. Asahi groups the stock artifacts by chip, stepping, board and vendor. The Linux reference driver uses the PTB as regulatory and calibration data alongside the firmware and handles additional device calibration separately. [Catalog](../evidence/2026-11-17-bluetooth-catalog.json), [Asahi package parser](https://github.com/AsahiLinux/asahi-installer/blob/main/asahi_firmware/bluetooth.py#L17-L116), [Linux firmware selection](https://github.com/torvalds/linux/blob/v6.12/drivers/bluetooth/hci_bcm4377.c#L1212-L1238), [Linux PTB setup](https://github.com/torvalds/linux/blob/v6.12/drivers/bluetooth/hci_bcm4377.c#L1444-L1465)

All eleven binaries fit a 256-byte header followed by three regions sized by little-endian fields in that header. The third begins with `BRCMcfgS`, followed by `BRCMcfgD` at region-relative offset 66. The embedded identity at offset 92 names the chip stepping, board, vendor and version. Removing leading zeroes from the decimal version components reproduces each filename version. AtlantisB, Capri and Santorini have a `3ANT` label. Actual antenna use remains unmeasured. [Region digests and embedded identities](../evidence/2026-11-17-bluetooth-catalog.json)

| Build group | First region | Second region | Configuration region |
| --- | ---: | ---: | ---: |
| Shikoku B1 MUR and USI | 116,248 B | 226,652 B | 14,582 B |
| Honshu B1 MUR and USI | 116,248 B | 226,652 B | 14,581 B |
| Kyushu B3 USI | 102,240 B | 115,536 B | 12,664 B |

The two Shikoku binaries match at 355,970 of 357,738 same-offset bytes. Both complete leading regions, totaling **342,900 bytes**, also match both Honshu binaries. All four configuration regions have different SHA-256 digests. Across all eleven binaries, the first two regions form five exact digest groups. The purpose of the first two regions on this controller remains unverified. [Catalog and byte comparison](../evidence/2026-11-17-bluetooth-host.json), [All region digests](../evidence/2026-11-17-bluetooth-catalog.json)

```sh
python3 tools/inspect_bluetooth_firmware.py --controller-version 24.2.551.4122
```

## Native macOS controls

| Surface | Verified access and limits |
| --- | --- |
| CoreBluetooth central and peripheral | Native SDK type-checks accepted scanning, connecting, GATT data exchange and notifications, advertising and BLE L2CAP declarations for applications. Apple exposes a connection-latency preference. Negotiated parameters remain unmeasured on this Mac. [Apple CoreBluetooth](https://developer.apple.com/documentation/corebluetooth), [Latency preference](https://developer.apple.com/documentation/corebluetooth/cbperipheralmanager/setdesiredconnectionlatency%28_%3Afor%3A%29) |
| RF telemetry and selection | CoreBluetooth has a connected-peer RSSI getter. An advertising transmit-power field describes a value reported by the remote advertiser when present. Apple documents automatic LE 2M negotiation with a compatible peer. A public arbitrary RF channel, PHY mode or conducted-power control remains unverified. [Advertised TX power](https://developer.apple.com/documentation/corebluetooth/cbadvertisementdatatxpowerlevelkey), [LE 2M negotiation](https://developer.apple.com/videos/play/wwdc2019/901/?time=217) |
| IOBluetooth | The SDK exposes controller power-state reads, temporary class-of-device settings, and classic connection APIs. These address the host controller or connection at the documented level. A live RF measurement remains a bench question. [Controller API](https://developer.apple.com/documentation/iobluetooth/iobluetoothhostcontroller), [Device API](https://developer.apple.com/documentation/iobluetooth/iobluetoothdevice) |
| Channel Sounding | Native compilation rejected `CBCentralManager.supports(.channelSounding)` and the session-cancellation method as unavailable on macOS. Apple's ranging sample uses an iOS 27 initiator on iPhone 17 or later and a compatible Bluetooth 6.3 peripheral. The check establishes native SDK availability. Ranging support in the raw controller remains unverified. [Apple Channel Sounding sample](https://developer.apple.com/documentation/corebluetooth/measuring-distance-between-devices-using-channel-sounding), [Session availability](https://developer.apple.com/documentation/corebluetooth/cbperipheral/startchannelsoundingsession%28_%3A%29) |

## Coexistence experiment

A separately managed test Mac and an owned BLE sensor can establish whether the documented GATT notification path remains responsive while Wi-Fi carries ordinary data. Record the notification intervals and lost messages, then align them with CoreWLAN snapshots and a fixed application workload. Hold the Wi-Fi band and width fixed for each trial and run a matching trial with the sensor idle. An independent connection for managing the test target preserves this Mac's uplink. The current host observation identifies both functions and the Bluetooth service flags. A simultaneous workload has yet to be measured. [CoreWLAN sampling](../README.md#reproduce-the-baseline), [A2337 radio test evidence](spectrum-sensing.md#a2337-lab-spectrum)
