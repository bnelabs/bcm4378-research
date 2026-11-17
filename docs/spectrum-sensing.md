# Spectrum coverage and sensing

## Stock channel map on this M1 Air

CoreWLAN's `supportedWLANChannels` getter returned two bands on 17 November 2026. The radio remained in station mode throughout this snapshot. The frequency ranges below group the reported **20 MHz channel centers**. Wider-channel entries list the number of driver-reported channel identifiers. [Local channel snapshot](../evidence/2026-11-17-corewlan-status.json), [CoreWLAN channel getter](https://developer.apple.com/documentation/corewlan/cwinterface/supportedwlanchannels%28%29)

| Band | Reported 20 MHz channel centers | 40 MHz | 80 MHz |
| --- | --- | ---: | ---: |
| 2.4 GHz | Ch 1–13, 2,412–2,472 MHz in 5 MHz steps | — | — |
| 5 GHz | Ch 36–64, 100–140, and 149–165 in steps of four channel numbers. Centers 5,180–5,320, 5,500–5,700, and 5,745–5,825 MHz. | 22 identifiers | 20 identifiers |

This is a channelized radio with gaps between the reported bands and groups. The stock list contains zero 6 GHz or 160 MHz entries. Apple publishes 2×2 Wi-Fi 6 up to 195 Mb/s PHY at 2.4 GHz HE20 and 1,200 Mb/s PHY at 5 GHz HE80. Driver permissions and availability are conditional on the operating region. The analog front end's continuous tuning limits remain unmeasured. [Apple Wi-Fi specifications](https://support.apple.com/en-au/guide/deployment/-dep268652e6c/web), [Apple M1 Air specifications](https://support.apple.com/en-us/111883)

## A2337 lab spectrum

The FCC filing and TÜV SÜD exhibits document these channel centers in MHz on A2337 samples. The FCC notes DFS and power-control requirements for the main U-NII-2A and 2C ranges. The straddling test frequencies appear separately. [FCC grants](https://fccid.io/BCGA2337#grants), [5 GHz test modes](https://device.report/m/9dbefd8fa57734334f25d9b4c27352a2b1333e4a7384c14f77fb813ec85822d7.pdf#page=5), [Apple DFS attestation](https://device.report/m/ac87d1b82111281c09a791d3ee888bd5f97a7443f03c4909bad073596f661d4b.pdf)

| Group | 20 MHz | 40 MHz | 80 MHz |
| --- | --- | --- | --- |
| U-NII-1 | 5180, 5200, 5220, 5240 | 5190, 5230 | 5210 |
| U-NII-2A | 5260, 5280, 5300, 5320 | 5270, 5310 | 5290 |
| U-NII-2C | 5500–5700 in 20 MHz steps | 5510–5670 in 40 MHz steps | 5530, 5610 |
| U-NII-2C/3 straddle | 5720 | 5710 | 5690 |
| U-NII-3 | 5745–5825 in 20 MHz steps | 5755, 5795 | 5775 |

### Match to the stock channel list

The 5 GHz comparison treats each reported channel number as a possible primary 20 MHz channel at `5000 + 5 × channel` MHz. A lab center matches when the stock list contains all of the primaries in its block at that width. This assigns every 5 GHz identifier in the fresh CoreWLAN listing to a tested block. The active channel 40 at 80 MHz falls in the 5,210 MHz block by this calculation. [CoreWLAN channel type](https://developer.apple.com/documentation/corewlan/cwchannel), [Comparison and underlying lists](../evidence/2026-11-17-corewlan-channel-plan.json)

| Width | Matched 5 GHz lab centers | Unmatched lab center | Primaries checked at that width |
| --- | ---: | ---: | --- |
| 20 MHz | 24 of 25 | 5,720 MHz | 144 |
| 40 MHz | 11 of 12 | 5,710 MHz | 140, 144 |
| 80 MHz | 5 of 6 | 5,690 MHz | 132, 136, 140, 144 |

Each unmatched center is from the A2337 straddle tests. None of its candidate primaries appeared at the corresponding width. Channels 132, 136 and 140 appeared at 20 MHz, and 132 and 136 also appeared in the 40 MHz list. The match compares the host's current advertised channel plan with a lab test plan. It leaves runtime availability under other operating conditions and physical tuning limits open. [A2337 5 GHz exhibit](https://device.report/m/9dbefd8fa57734334f25d9b4c27352a2b1333e4a7384c14f77fb813ec85822d7.pdf#page=5)

All seven installed regulatory profiles carry channel 144 in the general 5 GHz range. A read under registry country code `TR` confirmed its absence from the stock interface's 20 MHz list. The CLM comparison also traces the driver requests that depend on country context. [CLM channel tables and the active country plan](clm-channel-tables.md)

### Wi-Fi and Bluetooth lab modes

The lab measured simultaneous dual-band Wi-Fi in HT20 diversity modes. Separate pairings combined one Wi-Fi band with Classic Bluetooth. The single-band HE tests include HE80 MCS 7 with two streams at 5,210 MHz, both in single-user operation and with a 26-tone resource unit. Dual-band HE, triple transmission and dual association under stock macOS remain unverified. [A2337 RF tests and exhibit citations](a2337-rf-tests.md)

Bluetooth is authorized at 2,402–2,480 MHz. The classic Bluetooth test counted 79 hopping channels. The report also measured LE 1M and 2M, and two π/4-DQPSK lab modes called **HDR4** and **HDR8** at 2,404, 2,441 and 2,478 MHz. The reported 99% occupied bandwidths were 2.344 MHz and 4.550–4.560 MHz respectively. A separate Apple Watch report associates the same labels with 4 and 8 Mb/s. Rate and public access on this Mac remain unverified. [Classic Bluetooth test](https://device.report/m/f23d693e4f80d60e381d4984b15fc5007810b0506fba5d24963e328a6cb83c37.pdf#page=18), [A2337 HDR4](https://fccid.io/BCGA2337/Test-Report/Test-report-part1-4983141.pdf#page=8), [A2337 HDR8](https://fccid.io/BCGA2337/Test-Report/Test-report-part1-4983141.pdf#page=20), [A1978 comparison report](https://fccid.io/m/24fafd375904a7455de233e95862c736d9036949653151c13ecf93d0aa116c00.pdf)

The driver publishes bins for HE resource-unit sizes and trigger responses. The observed product widths, the lab waveforms, and the Radiotap capture fields provide the inputs for testing allocations within a Wi-Fi channel. [Wi-Fi 6 resource-unit evidence](he-ofdma.md)

## Research applicability

| Technique | What published work demonstrates | State on this Mac |
| --- | --- | --- |
| Aggregate link sensing | A MacBook Pro M3 study recorded RSSI using CoreWLAN at one-second intervals for a roaming experiment. [M3 CoreWLAN study, table 7](https://arxiv.org/html/2505.04174v1) | Timestamped RSSI, noise, PHY rate and channel are available through the repo tool. These are link measurements. |
| Packet-free spectral analysis | Airshark classified non-Wi-Fi interferers from FFT bins produced by Atheros AR9280 hardware. Broadcom describes AirIQ interference identification for its Max WiFi family. [Airshark paper](https://pages.cs.wisc.edu/~suman/pubs/airshark.pdf), [Broadcom AirIQ statement](https://investors.broadcom.com/news-releases/news-release-details/broadcom-announces-availability-industrys-first-complete) | The vendor statement is family-level. A BCM4378 FFT bin or power spectrum feed remains unverified. |
| Per-subcarrier CSI | Nexmon CSI's supported targets include other Broadcom chip families. AX-CSI used a BCM43684 testbed. [Nexmon CSI support list](https://github.com/seemoo-lab/nexmon_csi/blob/master/README.md), [AX-CSI paper](https://ans.unibs.it/assets/documents/axcsi.pdf) | The shared Apple driver has a CSI adapter. The live BCM4378 firmware words leave its legacy `csi` gate clear. A public macOS CSI feed remains unverified. [CSI gate trace](firmware-capabilities.md#csi-sensing-in-the-shared-driver) |
| Radar-like range and motion | LiveSense uses synchronized CSI from Intel AX211 or BE201 at 40 Hz or above. Its authors report range, radial velocity and micro-motion sensing. [LiveSense preprint](https://arxiv.org/abs/2603.06545), [Monostatic presence study](https://arxiv.org/abs/2603.10845) | The stock BCM4378 readout exposes aggregate metrics. The synchronized measurements required by these methods remain unverified on this radio. |
| Wi-Fi ranging | FTM ranging requires a supported timing exchange at both ends. Researchers measured accuracy with supported commercial devices. [Measured FTM accuracy](https://www.jstage.jst.go.jp/article/comex/9/12/9_2020COL0001/_article) | The live PCIe driver reports ranging eligibility and the firmware reports `proxd`. The infrastructure ranging capability handler returns unsupported. A ranging result remains unmeasured. [Ranging gate trace](firmware-capabilities.md#ranging-on-the-bcm4378) |
| WLAN sensing standard | IEEE published 802.11bf-2025 in September 2025. It defines sensing procedures across several bands. [IEEE working group](https://ieee802.org/11/overview.html), [NIST sensing study](https://www.nist.gov/publications/ieee-80211bf-enabling-widespread-adoption-wi-fi-sensing) | The M1 Air has a documented Wi-Fi 6 radio. An 802.11bf capability claim for the BCM4378 would require new evidence. |

### Timing and ranging evidence

All three installed BCM4378 images contain the same 19 proximity-related printable strings. The 250 stock NVRAM paths include three proximity assignments across all board variants, including a scalar and two four-entry offset arrays for cores 0 and 1. This establishes board-provisioned proximity data on Shikoku. The units, protocol, firmware use and actual ranging results remain open. Broadcom's published BCM4383 host code checks firmware capabilities separately before advertising Fine Timing Measurement (FTM). [Stock firmware and profile evidence](../evidence/2026-11-17-wifi-timing-capabilities.json), [Broadcom capability check](https://android.googlesource.com/kernel/google-modules/wlan/bcmdhd/bcm4383/+/3b1a081640892e16ac658f66a0b0d026735922fe/dhd_rtt.c#6078)

Both signed Apple host driver slices contain FTM and Target Wake Time (TWT) markers. The TWT strings correspond to diagnostic argument labels. Code references link the proximity support messages to ranging-status diagnostics. Asahi sets four TWT bits in its shared HE table after the general HE gate. The reviewed `cfg80211.c` and `core.c` for both pinned `brcmfmac` trees contain no registration for the standard peer measurement path. Live BCM4378 FTM exchanges and TWT scheduling remain unverified. [Driver diagnostic provenance](driver-timing-provenance.md), [Scoped source and artifact checks](../evidence/2026-11-17-wifi-timing-capabilities.json), [Asahi HE table](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7392-L7410), [Linux peer measurement gate](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/net/wireless/pmsr.c#L414-L428)

Apple documents a 56-bit random starting Timing Synchronization Function (TSF) offset in peer-to-peer and access point modes on late-2020 and newer Macs with macOS 12.0.1 or later. The offset changes when the interface MAC address changes. Align receiver captures against a common observer clock when comparing timing across peer sessions. [Apple Platform Security](https://support.apple.com/en-ca/guide/security/sec31e483abf/web)

The packet-timing investigation traces the PCIe clock modes and verifies stock macOS socket timestamps. Saved Radiotap captures can carry both a receive-side TSF time and a timestamp sampled earlier in the PHY. [Packet timestamp evidence](packet-timestamps.md)

## Interface activity and PHY rate

The sampler's optional `--traffic` mode pairs CoreWLAN with the stock `netstat` link-layer row for the same interface. Apple sources its interface totals from unsigned 64-bit byte and packet fields. The analyzer uses adjacent samples from the same interface with increasing timestamps and nondecreasing counters. It totals bytes and divides by the elapsed time covered by those intervals. Missing samples, counter decreases and incomparable intervals have separate counts. [Apple netstat implementation](https://github.com/apple-oss-distributions/network_cmds/blob/main/netstat.tproj/if.c), [Apple interface counter definitions](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/net/if_var.h)

The live run had 21 station-mode samples on `en0`, channel 40 at 80 MHz. Across 11.87 seconds of comparable intervals, the interface received 25,981,651 bytes and sent 1,256,886 bytes. The receive and transmit averages were 17.51 and 0.85 Mb/s. CoreWLAN returned 432 Mb/s transmit PHY rate, −67 dBm RSSI and raw transmit-power integer `1496` on every poll. A bounded HTTPS request during the run returned HTTP 200 with a 67,838-byte body. The counter interval bracketing that request included 7,491,093 received bytes. These totals describe all traffic observed at the interface, including activity outside that request. [Paired samples](../evidence/2026-11-17-link-activity-sample.json), [Transfer and interval summary](../evidence/2026-11-17-link-activity-observation.json), [CoreWLAN rate getter](https://developer.apple.com/documentation/corewlan/cwinterface/transmitrate%28%29)

Aggregate activity helps distinguish an idle connection from a connection moving data with steady radio readouts. A controlled workload and independent RF measurement are needed to relate rate and traffic changes to an obstruction or source of interference.

### Wi-Fi 6 rate ambiguity

The installed driver's transmit-rate handler delegates to its link-quality module. On an associated interface, both binary slices divide an unsigned 32-bit rate metric by 1,000 with integer truncation. CoreWLAN dispatches the public query through CoreWiFi. The metric's update age and the per-frame source remain unmeasured. [Driver and wrapper evidence](../evidence/2026-11-17-tx-rate-provenance.json), [CoreWLAN rate getter](https://developer.apple.com/documentation/corewlan/cwinterface/transmitrate%28%29)

The optional offline rate model enumerates MCS 0–11, one or two spatial streams and the three HE guard intervals. It assumes full-channel HE transmission, no dual-carrier modulation and whole-Mb/s truncation. All 21 saved HE80 samples and nine fresh reads reported 432 Mb/s on channel 40. That rate admits two nominal modes in the model. [Mode calculation and observations](../evidence/2026-11-17-tx-rate-provenance.json), [Cisco 802.11ax tone and symbol timing](https://www.cisco.com/c/en/us/products/collateral/wireless/white-paper-c11-740788.html), [Cisco rate table](https://www.cisco.com/c/en/us/support/docs/wireless-mobility/wireless-lan-wlan/212892-802-11ac-wireless-throughput-testing-and.html)

| MCS | Modulation | Spatial streams | Guard interval | Nominal PHY rate |
| ---: | --- | ---: | ---: | ---: |
| 4 | 16-QAM | 2 | 800 ns | 432.353 Mb/s |
| 8 | 256-QAM | 1 | 800 ns | 432.353 Mb/s |

An association's reported width can exceed the bandwidth of an individual transmission. A timestamped uplink MCS and stream-count observation from the owned AP or the separate test station can distinguish the two candidates and detect cases where the full-channel model does not apply.

### What RSSI and noise measure

In both installed driver slices, the infrastructure RSSI handler receives four signed antenna slots from a firmware getter. It averages the nonzero slots with signed integer truncation. CoreWiFi reads the first value in its single-value case and the aggregate field otherwise. For example, a pair of −64 and −71 dBm truncates to the same −67 dBm reported for two −67 dBm values. The four-slot format establishes the reply layout, and the physical chain count comes from separate board evidence. [Signal provenance](../evidence/2026-11-17-signal-provenance.json), [Board chain declarations](firmware-layout.md#nvram-chain-declarations), [Apple RSSI documentation](https://developer.apple.com/documentation/corewlan/cwinterface/rssivalue%28%29)

The driver's noise getter goes through the associated BSS manager. CoreWiFi requests noise separately. Across sixteen pairs of public calls, RSSI was −68 dBm in fourteen and −69 dBm in two. Noise remained −91 dBm. The median host call durations were 3.779 ms for RSSI and 0.948 ms for noise. The call durations establish the polling overhead. RF acquisition time, freshness and alignment of the two values remain unknown, so the link diary reports their difference as a link-margin estimate. [Live getter timing](../evidence/2026-11-17-signal-provenance.json), [Apple noise documentation](https://developer.apple.com/documentation/corewlan/cwinterface/noisemeasurement%28%29)

## Experiments worth doing

1. **Passive link diary.** Run the sampler while walking, closing a door or moving owned equipment in a known test space. Record event times, hold the Mac and AP positions fixed, and compare repeated labeled intervals on the same channel and width. The 16-sample baseline took 7.67 seconds. A second 36-sample, 35.50-second series on channel 40 at 80 MHz also returned −67 dBm RSSI, −88 dBm noise and a 432 Mb/s PHY rate every time. The new analyzer measures repeat counts, reported link margin, and unavailable values directly from saved captures. A usable sensing result needs repeated and held-out labeled trials. [Baseline readings](../evidence/2026-11-17-link-sample.json), [Longer series](../evidence/2026-11-17-link-power-sample.json), [Apple link-quality API](https://developer.apple.com/documentation/corewlan/cweventdelegate/linkqualitydidchangeforwifiinterface%28withname%3Arssi%3Atransmitrate%3A%29)
2. **Correlate interference without moving the uplink.** Use an independent receive-only spectrum sensor and align its timestamps with CoreWLAN readings. Look for repeated RF energy bursts coinciding with sustained PHY-rate degradation on the connected channel. Repeat at multiple sensor positions to localize a candidate source. Airshark used real spectral samples, and WiFiNet demonstrated source localization with synchronized receivers. [Airshark](https://pages.cs.wisc.edu/~suman/pubs/airshark.pdf), [WiFiNet study](https://www.usenix.org/conference/nsdi12/technical-sessions/presentation/rayanchu), [NTIA RF measurement methods](https://redbook.ntia.gov/view/M-1)
3. **Apple-to-Apple fallback transfer.** Design a short-lived peer transfer for a file or work queue when a cloud service is unavailable. Test on a spare Apple device pair with an existing infrastructure connection. Record successful delivery and infrastructure latency during discovery and transfer. Apple documents performance effects from enabling peer-to-peer Wi-Fi. [Apple Network framework peer-to-peer guidance](https://developer.apple.com/documentation/technotes/tn3213-moving-from-multipeer-connectivity-to-network-framework#Enable-peer-to-peer-Wi-Fi)
4. **Separate CSI sensing bench.** A chipset with supported CSI telemetry can supply per-subcarrier measurements while this Mac records data and retains its network role. Espressif documents CSI on the dual-band ESP32-C5. Compare repeatability and false-positive rates from CSI against the aggregate CoreWLAN baseline. [ESP32-C5 CSI documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c5/api-guides/wifi-driver/wifi-vendor-features.html)
