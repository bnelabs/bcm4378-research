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

The 2.4 GHz lab report includes HE20 measurements at 2,412, 2,442 and 2,472 MHz. Simultaneous dual-band WLAN was tested on one A2337 in a lab mode. Additional tests paired one WLAN band with classic Bluetooth. Dual association under stock macOS and transmission combining both WLAN bands with Bluetooth remain unverified. [2.4 GHz HE20 exhibit](https://fccid.io/BCGA2337/Test-Report/Test-report-BT-LE-part1-4983143.pdf#page=33), [Simultaneous-transmission exhibit](https://fccid.io/BCGA2337/Test-Report/Simultaneous-transmission-report-4983630.pdf#page=7)

Bluetooth is authorized at 2,402–2,480 MHz. The classic Bluetooth test counted 79 hopping channels. The report also measured LE 1M and 2M, and two π/4-DQPSK lab modes called **HDR4** and **HDR8** at 2,404, 2,441 and 2,478 MHz. The reported 99% occupied bandwidths were 2.344 MHz and 4.550–4.560 MHz respectively. A separate Apple Watch report associates the same labels with 4 and 8 Mb/s. Rate and public access on this Mac remain unverified. [Classic Bluetooth test](https://device.report/m/f23d693e4f80d60e381d4984b15fc5007810b0506fba5d24963e328a6cb83c37.pdf#page=18), [A2337 HDR4](https://fccid.io/BCGA2337/Test-Report/Test-report-part1-4983141.pdf#page=8), [A2337 HDR8](https://fccid.io/BCGA2337/Test-Report/Test-report-part1-4983141.pdf#page=20), [A1978 comparison report](https://fccid.io/m/24fafd375904a7455de233e95862c736d9036949653151c13ecf93d0aa116c00.pdf)

## Research applicability

| Technique | What published work demonstrates | State on this Mac |
| --- | --- | --- |
| Aggregate link sensing | A MacBook Pro M3 study recorded RSSI using CoreWLAN at one-second intervals for a roaming experiment. [M3 CoreWLAN study, table 7](https://arxiv.org/html/2505.04174v1) | Timestamped RSSI, noise, PHY rate and channel are available through the repo tool. These are link measurements. |
| Packet-free spectral analysis | Airshark classified non-Wi-Fi interferers from FFT bins produced by Atheros AR9280 hardware. Broadcom describes AirIQ interference identification for its Max WiFi family. [Airshark paper](https://pages.cs.wisc.edu/~suman/pubs/airshark.pdf), [Broadcom AirIQ statement](https://investors.broadcom.com/news-releases/news-release-details/broadcom-announces-availability-industrys-first-complete) | The vendor statement is family-level. A BCM4378 FFT bin or power spectrum feed remains unverified. |
| Per-subcarrier CSI | Nexmon CSI's supported targets include other Broadcom chip families. AX-CSI used a BCM43684 testbed. [Nexmon CSI support list](https://github.com/seemoo-lab/nexmon_csi/blob/master/README.md), [AX-CSI paper](https://ans.unibs.it/assets/documents/axcsi.pdf) | Neither project demonstrates the BCM4378. A public macOS CSI feed remains unverified. |
| Radar-like range and motion | LiveSense uses synchronized CSI from Intel AX211 or BE201 at 40 Hz or above. Its authors report range, radial velocity and micro-motion sensing. [LiveSense preprint](https://arxiv.org/abs/2603.06545), [Monostatic presence study](https://arxiv.org/abs/2603.10845) | The stock BCM4378 readout exposes aggregate metrics. The synchronized measurements required by these methods remain unverified on this radio. |
| Wi-Fi ranging | FTM ranging requires a supported timing exchange at both ends. Researchers measured accuracy with supported commercial devices. [Measured FTM accuracy](https://www.jstage.jst.go.jp/article/comex/9/12/9_2020COL0001/_article) | A public BCM4378 macOS FTM API and ranging result remain unverified. |
| WLAN sensing standard | IEEE published 802.11bf-2025 in September 2025. It defines sensing procedures across several bands. [IEEE working group](https://ieee802.org/11/overview.html), [NIST sensing study](https://www.nist.gov/publications/ieee-80211bf-enabling-widespread-adoption-wi-fi-sensing) | The M1 Air has a documented Wi-Fi 6 radio. An 802.11bf capability claim for the BCM4378 would require new evidence. |

## Experiments worth doing

1. **Passive link diary.** Run the sampler while walking, closing a door or moving owned equipment in a known test space. Record event times, hold the Mac and AP positions fixed, and compare repeated labeled intervals on the same channel and width. The 16-sample baseline on this Mac took 7.67 seconds and returned the same values at every read: −67 dBm RSSI, −88 dBm noise and 432 Mb/s transmit PHY rate. A usable sensing result needs separately repeated and held-out trials. [Baseline readings](../evidence/2026-11-17-link-sample.json), [Apple link-quality API](https://developer.apple.com/documentation/corewlan/cweventdelegate/linkqualitydidchangeforwifiinterface%28withname%3Arssi%3Atransmitrate%3A%29)
2. **Correlate interference without moving the uplink.** Use an independent receive-only spectrum sensor and align its timestamps with CoreWLAN readings. Look for repeated RF energy bursts coinciding with sustained PHY-rate degradation on the connected channel. Repeat at multiple sensor positions to localize a candidate source. Airshark used real spectral samples, and WiFiNet demonstrated source localization with synchronized receivers. [Airshark](https://pages.cs.wisc.edu/~suman/pubs/airshark.pdf), [WiFiNet study](https://www.usenix.org/conference/nsdi12/technical-sessions/presentation/rayanchu), [NTIA RF measurement methods](https://redbook.ntia.gov/view/M-1)
3. **Apple-to-Apple fallback transfer.** Design a short-lived peer transfer for a file or work queue when a cloud service is unavailable. Test on a spare Apple device pair with an existing infrastructure connection. Record successful delivery and infrastructure latency during discovery and transfer. Apple documents performance effects from enabling peer-to-peer Wi-Fi. [Apple Network framework peer-to-peer guidance](https://developer.apple.com/documentation/technotes/tn3213-moving-from-multipeer-connectivity-to-network-framework#Enable-peer-to-peer-Wi-Fi)
4. **Separate CSI sensing bench.** A chipset with supported CSI telemetry can supply per-subcarrier measurements while this Mac records data and retains its network role. Espressif documents CSI on the dual-band ESP32-C5. Compare repeatability and false-positive rates from CSI against the aggregate CoreWLAN baseline. [ESP32-C5 CSI documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c5/api-guides/wifi-driver/wifi-vendor-features.html)
