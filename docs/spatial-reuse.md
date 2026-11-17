# BCM4378 BSS coloring and spatial reuse

The running A2337 firmware advertises `he`. I/O Registry publishes overlapping basic service set (OBSS) clear-channel assessment labels for `en0` and `awdl0`. Those labels establish that the driver exposes CCA diagnostics for overlapping Wi-Fi networks. The current AP's BSS color, spatial reuse policy, and use of concurrent transmissions remain unmeasured. [Live evidence](../evidence/2026-11-17-spatial-reuse.json), [CCA provenance](cca-provenance.md)

## What the signed driver does

`AppleBCMWLANCore::IssueFwCap` maps the exact legacy word `obss_hw` to feature bit 101 in both signed DriverKit slices. The `setupFirmware` path tests that bit before requesting hardware mitigation through `enableObssMitigation`. The driver's OBSS detection event handler can log an available channel specification from the event. The scope of that path is channel overlap detection and the driver's corresponding mitigation request. [Signed methods and feature bit](../evidence/2026-11-17-spatial-reuse.json)

The `obss_hw` word is absent from the live legacy capability response. The legacy parser therefore clears bit 101 on this input. The extended firmware response and actual mitigation state remain unmeasured. The CCA trace identifies how the driver obtains overlapping-network reports and how requesting live values can enter a firmware command path. [Firmware capability provenance](firmware-capabilities.md), [IOReport update path](cca-provenance.md#ioreport-catalog-and-sample-path)

CoreWLAN documents a cache of scan results and an information-element property on cached networks. A read of the associated BSSID returned nil in this session, so the cache probe could not identify the connected AP. The installed SDK documents an authorized Location Services dependency for that identifier. [CoreWLAN cache getter](https://developer.apple.com/documentation/corewlan/cwinterface/cachedscanresults%28%29), [CoreWLAN information elements](https://developer.apple.com/documentation/corewlan/cwnetwork/informationelementdata), [Cache probe result](../evidence/2026-11-17-spatial-reuse.json)

## What an association capture can establish

BSS color is a six-bit classifier for HE transmissions. HE Operation advertises a color along with partial-color and disabled flags. The HE PHY header can carry the color on individual transmissions. The station uses that context to distinguish its own BSS from overlapping traffic. The OBSS packet-detection mechanism can permit transmission during weaker overlapping traffic subject to a transmit power constraint. Parameterized spatial reuse (PSR) is another mechanism with its own support bit. [IEEE 802.11ax](https://ieeexplore.ieee.org/document/9442429), [OBSS-PD analysis and simulations](https://ieeexplore.ieee.org/abstract/document/9566607), [HE Operation field definitions](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/include/linux/ieee80211-he.h#L533-L545), [Radiotap HE field](https://radiotap.org/fields/HE.html)

The Spatial Reuse Parameter Set has an SR Control octet that describes allowed behavior and which optional offsets and bitmaps are present. An SRG is a spatial reuse group. Its optional data identifies group members using color and partial BSSID bitmaps and carries minimum and maximum OBSS packet-detection offsets. The fields are offsets in dB. Measuring the station's applied thresholds requires a separate observation. [Linux field definitions and size checks](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/include/linux/ieee80211-he.h#L767-L801), [mac80211 parser](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/net/mac80211/he.c#L238-L274)

| SR Control bit | Advertised meaning when set |
| ---: | --- |
| 0 | Parameterized spatial reuse disallowed |
| 1 | Non-SRG OBSS packet-detection spatial reuse disallowed |
| 2 | Non-SRG maximum offset present |
| 3 | SRG offsets and bitmaps present |
| 4 | HE-SIG-A spatial reuse value 15 allowed |

The pinned Asahi `brcmfmac` driver reads the firmware's default HE capabilities for diagnostics. It separately builds its station `wiphy` capability table. Its constructed HE PHY capability byte 7 leaves the PSR-based spatial reuse bit clear. A capture of the association would show which capabilities the full-MAC firmware actually places on the air. [Asahi station template](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7378-L7463), [Asahi firmware capability read](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7523-L7532), [PSR support bit definition](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/include/linux/ieee80211-he.h#L394-L399)

## Reproducing the evidence and testing a live policy

```sh
python3 tools/read_cca_legend.py
python3 tools/summarize_he_capture.py --spatial-reuse /path/to/bench-capture.pcapng
```

The capture summary uses TShark to count records containing each selected field and tally its decoded values. It covers Radiotap HE color and its known flag, HE Operation color and flags, the HE PHY PSR support bit, and the advertised SR controls and offsets. Each field is counted independently because one management record can include several advertisements. The new mode passed a five-record synthetic fixture. The default HE resource-unit report matched its previous fixture. [Capture tool](../tools/summarize_he_capture.py), [Fixture readback](../evidence/2026-11-17-spatial-reuse.json), [Wireshark WLAN fields](https://www.wireshark.org/docs/dfref/w/wlan.html)

1. **Validate the AP policy.** Use a second A2337, two managed APs on the same channel, and independent capture receivers. Set and record BSS colors and supported spatial reuse controls on the bench APs. A hostapd implementation can expose `he_bss_color`, `he_spr_sr_control`, and the optional offsets and group settings. Confirm the resulting AP advertisements and inspect station association frames for capabilities.
2. **Measure channel sharing.** Keep channel width, placement, and offered load fixed across runs. Compare per-BSS goodput, retries, and tail delay. Use synchronized capture to establish which frames overlap and record delivery or acknowledgment on both links. Confirm the BSS identity before interpreting a repeated color as a collision. Published analyses find that interference geometry affects the reuse gain, so repeat at different AP separations before applying a result to another site. [Hostapd configuration reference](https://android.googlesource.com/platform/external/wpa_supplicant_8/%2B/refs/heads/android16-s2-release/hostapd/hostapd.conf), [OBSS-PD topology analysis](https://ieeexplore.ieee.org/abstract/document/9566607)
