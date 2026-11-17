# Wi-Fi beamforming and sounding on the BCM4378

A beamformer sends a sounding signal so the beamformee can estimate the channel and return compressed feedback. The transmitter can use that feedback to choose per-chain weights. Single-user (SU) and multi-user (MU) describe whose signals the transmitter serves. The same station can advertise several roles. [Wi-BFI paper, §2](https://arxiv.org/abs/2309.04408)

## A2337 hardware and macOS

Apple specifies two data streams and up to 80 MHz at 5 GHz for the M1 MacBook Air. Its 5 GHz compliance report lists two-core transmit beamforming test modes at HT20/40 and VHT20/40/80. Table 42 gives a concrete measurement at 5,210 MHz using VHT80 MCS7 with one data stream and both cores. It records 7.98 and 7.84 dBm at the two conducted outputs, for a combined 10.92 dBm. The test establishes two-chain transmit beamforming in a lab configuration. Beam direction, link gain, and normal association behavior remain open for a bench test. [Apple Wi-Fi specifications](https://support.apple.com/en-au/guide/deployment/-dep268652e6c/web), [A2337 report §1.4.2](https://device.report/m/9dbefd8fa57734334f25d9b4c27352a2b1333e4a7384c14f77fb813ec85822d7.pdf#page=5), [Table 42](https://device.report/m/9dbefd8fa57734334f25d9b4c27352a2b1333e4a7384c14f77fb813ec85822d7.pdf#page=19)

The running firmware `18.20.511.0.7.8.207` publishes SU beamformer, SU beamformee, and MU beamformee in its legacy `FWCap` string. Both distinct installed B1 images contain words for all four roles, including MU beamformer, which is absent from the live legacy response. The selected image also contains format strings for explicit and implicit beamforming mode, last sounding status, transmitted null-data packets, and received reports. These are strings in the file. Live values and the role used on this association remain unmeasured. [Firmware selection](firmware-layout.md), [Legacy capability query](firmware-capabilities.md), [Registry and image evidence](../evidence/2026-11-17-beamforming.json)

The key search found zero beamforming-related matches among the ten distinct installed B1 NVRAM texts and in the Shikoku PlatformConfig plist. The scoped live registry search and the public IOReport legend label search also returned zero matches. The evidence records the terms searched. The searches cover published names and textual keys. [Search scope and file identities](../evidence/2026-11-17-beamforming.json)

## Linux capability reporting

Both pinned brcmfmac versions read `txbf_bfe_cap` and `txbf_bfr_cap` when initializing VHT. The VHT builder maps the returned SU and MU bits into the kernel's local capabilities. With beamforming capability and more than one transmit stream, the builder encodes the transmit sounding dimension field as `txstreams - 1` and fills the beamformee space-time-stream field separately. [Stable Linux reads](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7394-L7412), [VHT builder](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7326-L7343), [Asahi VHT paths](../evidence/2026-11-17-beamforming.json)

Asahi builds the HE station capabilities from a separate fixed table. The table sets SU beamformer, SU beamformee, triggered SU feedback, and triggered MU partial-bandwidth feedback. Its HE MU beamformer bit is clear. The beamformee fields encode support for sounding from up to eight space-time streams at up to 80 MHz and four above 80 MHz. The `0xfffa` HE MCS map at up to 80 MHz independently describes two transmit and two receive data streams with MCS 0–11. The sounding figures describe the peer's sounding signal the beamformee can process. The table also includes a 160 MHz flag. Apple specifies an 80 MHz limit on the A2337, and Asahi's reported and negotiated widths on this board remain to be measured. [Asahi HE builder](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7378-L7475), [HE field masks](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/include/linux/ieee80211-he.h#L345-L365)

## Reading saved captures

```sh
python3 tools/summarize_he_capture.py --beamforming /path/to/bench-capture.pcapng
```

The tool reads saved frames with TShark. It counts VHT and HE capability bits, null-data packet announcements, trigger types, compressed feedback metadata, and known Radiotap beamforming flags. The feedback `Nr` and `Nc` indices are the matrix row and column counts minus one. The NDPA announces the upcoming sounding packet. The report describes the beamformee's response. Radiotap records the PHY flag when the recorder reports it as known. The VHT beamformed flag applies to SU transmissions. Counts are independent per field and describe capture records, including repeated or segmented frames. [Wireshark WLAN fields](https://www.wireshark.org/docs/dfref/w/wlan.html), [Radiotap VHT](https://radiotap.org/fields/VHT.html), [Radiotap HE](https://radiotap.org/fields/HE.html)

| Wi-BFI sample | Capture records | Decoded NDPA | Feedback MIMO control | Feedback dimensions |
| --- | ---: | ---: | ---: | --- |
| VHT40 SU | 631 | 0 | 631 | 3 rows × 1 column |
| HE80 SU | 272,634 | 602 | 555 | 4 rows × 2 columns |

The public HE trace also has 8,141 records with a known HE TxBF flag, including 6,756 with the bit set. The files came from the Wi-BFI authors and serve as parser fixtures. The hashes and nonempty field histograms are recorded with the evidence. [Pinned Wi-BFI captures](https://github.com/kfoysalhaque/Wi-BFI/tree/47ca7f842d6efdff2f83b981a7c119327e8dc2d6/traces), [TShark 4.6.9 results](../evidence/2026-11-17-beamforming.json)

## Measurements for a separate A2337

Use an owned AP and an independent recorder that supplies the PHY flags. Keep the channel, width, traffic direction, and client position fixed. Use the AP's documented SU beamforming option if available and repeat on/off runs. Identify the A2337's direction from its association and sounding exchange. An AP announcement followed by a matching report from the A2337 establishes the station's beamformee role. A station announcement and matching report from the AP establishes the reverse role. Retain retry rate, signal, and throughput for each run. Use two active owned clients and AP scheduling evidence to check actual MU traffic separately from the MU capability bits.

A fixed-link experiment can also test whether compressed feedback helps detect a change in the path, such as placing a reflector at a repeatable position. Compare the feedback under known conditions and on held-out runs. Wi-BFI shows how to reconstruct a quantized steering representation from the feedback. Link diagnosis and controlled sensing require their own measurements on the BCM4378. [Wi-BFI method](https://arxiv.org/abs/2309.04408)
