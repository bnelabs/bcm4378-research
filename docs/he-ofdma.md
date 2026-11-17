# BCM4378 Wi-Fi 6 resource units and trigger frames

On the A2337, CoreWLAN reported `en0` associated in 802.11ax mode on 5 GHz channel 40 with an 80 MHz channel width. Its supported-channel list offered 20 MHz at 2.4 GHz and 20, 40, and 80 MHz at 5 GHz. Apple's product specifications give the same maximum HE widths. The running Shikoku firmware publishes `he` and `multi-user-beamformee` in its legacy capability string. Actual resource-unit assignments remain unmeasured. [CoreWLAN PHY getter](https://developer.apple.com/documentation/corewlan/cwinterface/activephymode%28%29), [Apple Wi-Fi specifications](https://support.apple.com/en-au/guide/deployment/-dep268652e6c/web), [Live sample](../evidence/2026-11-17-he-ofdma.json)

## Channel width and resource-unit size

In an HE OFDMA exchange, the access point schedules portions of the channel for individual stations. The table gives nominal tone bandwidth, calculated as tone count times the HE spacing of 78.125 kHz. The FCC occupied-bandwidth measurements use their own RF test method. The minimum channel-width column describes the standard geometry. Apple's product specification bounds the A2337 implementation. [IEEE 802.11ax specification](https://ieeexplore.ieee.org/document/9442429), [Rohde & Schwarz HE PHY measurements and tone plan](https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/premiumdownloads/premium_dl_brochures_and_datasheets/premium_dl_whitepaper/IEEE-802-11ax-Technology-Introduction_wp_3609-9470-52_v0100.pdf), [A2337 RF tests](a2337-rf-tests.md)

| HE resource unit | Nominal tone bandwidth | Minimum channel-width class |
| --- | ---: | --- |
| 26 tones | 2.03 MHz | 20 MHz |
| 52 tones | 4.06 MHz | 20 MHz |
| 106 tones | 8.28 MHz | 20 MHz |
| 242 tones | 18.91 MHz | 20 MHz |
| 484 tones | 37.81 MHz | 40 MHz |
| 996 tones | 77.81 MHz | 80 MHz |
| 2×996 tones | 155.63 MHz | 160 MHz including 80+80 MHz |

The existing 2.4 GHz exhibit review records HE20 tests and 26- through 242-tone cases. The 2.4 GHz PDF was unavailable for direct recheck. The 5 GHz report lists HE20, HE40, and HE80 tests with allocations through 996 tones where the width allows. At **5,210 MHz**, TÜV SÜD reported corrected conducted power spectral density of **−6.86 dBm/MHz** for the single-user HE80 waveform and **+6.38 dBm/MHz** for the HE80 waveform using a 26-tone allocation. Both used MCS 7 with two spatial streams in the US lab profile. The **13.24 dB** difference compares those two lab settings. Live station PSD remains unmeasured. [A2337 exhibit review](a2337-rf-tests.md#80211ax-waveforms-and-wi-fi-antenna-paths), [TÜV SÜD 75949395-12, Tables 255 and 257](https://device.report/m/9dbefd8fa57734334f25d9b4c27352a2b1333e4a7384c14f77fb813ec85822d7.pdf#page=88)

## The published counter catalog

| Legend group on macOS 26B131 | Labels observed |
| --- | --- |
| `Chip` Tx and Rx OFDMA RU counters | 26, 52, 106, 242, 484, and 996 tones in each direction |
| `Slice 0` and `Slice 1` Tx and Rx OFDMA RU counters | The same six sizes plus a 2×996-tone bucket |
| `MPDUs per RU` | 26- and 242-tone receive aggregation buckets at 20, 40, and 80 MHz |
| Frame counters for each published slice | Transmit trigger frames and trigger-based PPDUs, receive SU and MU PPDUs, and receive trigger types including basic, MU-RTS, buffer status polling, and MU Block Ack request |

The signed driver's `parseV30CntContainer` forwards HE counter records to `reportHeCntPerSlice`. The `initHeWlCntReporter` path registers the transmit and receive groups. There is a separate reporter for slice-level control and data frame counters. The same symbols and calls are present in both installed driver slices. The 2×996 entries identify a bucket in the reporter schema. Apple's 80 MHz product limit and the A2337 test evidence bound the width used here. The live inspection collected names from the published registry. The report update path and actual values need a bench measurement. [Driver trace and allowlisted labels](../evidence/2026-11-17-he-ofdma.json), [IOReport sample path](cca-provenance.md#ioreport-catalog-and-sample-path)

The signed driver also routes the internal `WCL_ULOFDMA_STATE` request to `AppleBCMWLAN11axAdapter::configureUpLinkOFDMA`. That method normalizes the requested state to a Boolean, selects a newer message format above firmware interface version 20, and has synchronous and asynchronous paths to the `he` firmware variable. A separate handler checks the uplink OFDMA disable event version. These paths establish the internal control and event handling present in the binary. The active firmware interface version and the result of applying a state request remain unmeasured. [Signed driver entry points](../evidence/2026-11-17-he-ofdma.json)

Asahi's pinned station rate decoder exposes HE MCS, stream count, dual-carrier modulation, and guard interval. Its bandwidth output uses the width in the firmware ratespec. This decoder leaves the per-user HE RU field unset. For both macOS and Asahi, a rate readout provides useful link context for a capture-based RU test. [Asahi ratespec decoder](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L2910-L2970)

## Reproduction and bench measurement

```sh
swift tools/read_wifi_status.swift
python3 tools/read_macos_inventory.py
python3 tools/summarize_he_capture.py /path/to/bench-capture.pcapng
```

The inventory publishes the selected names under `wifi.he_ru_counter_legend`. The capture tool uses TShark to read an existing file and counts capture records by HE format and data width or RU. An RU code contributes to a known bucket only when the Radiotap known flag is set. Unknown and reserved values are counted explicitly. A capture record can represent one MPDU or one captured user within a shared PHY transmission. Unique PHY transmissions, transmit duration, and full-channel occupancy need additional evidence. HE-MU allocation metadata can record the other portions of the channel when the capture device supplies it. The tool passed an eight-record synthetic fixture with TShark 4.6.9. [Radiotap HE field](https://radiotap.org/fields/HE.html), [HE-MU field](https://radiotap.org/fields/HE-MU.html), [Fixture result](../evidence/2026-11-17-he-ofdma.json)

1. **Measure whether small flows share the channel.** Use a second A2337 with console access, a controlled AP, and an HE-capable independent receiver. Keep channel, width, offered traffic, and client positions fixed. Compare the AP's documented uplink and downlink OFDMA policies while collecting a benchmark on two associated clients. Check packet delay, AP-reported allocations, and Radiotap HE-MU and trigger-response records.
2. **Estimate scheduled tone time.** For same-channel test runs, combine known RU position and tone count with the duration of the HE data portion. Match records belonging to the same PHY transmission before adding up allocations. Use the result to compare spectrum sharing under different AP policies. A separate RF measurement supplies energy and interference outside decoded Wi-Fi transmissions.
3. **Use dedicated hardware for coordinated transmitters.** An openwifi and White Rabbit study measured two time- and frequency-aligned transmitters on separate 106-tone allocations. Its FPGA radios and wired synchronization give a reference for experiments on independent AP scheduling. The A2337 evidence here covers a managed station and its reporting paths. [Havinga et al., coordinated OFDMA study](https://arxiv.org/abs/2507.10210)
