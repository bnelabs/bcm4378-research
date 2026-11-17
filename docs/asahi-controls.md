# BCM4378 Wi-Fi controls on Linux and Asahi

This comparison uses upstream stable Linux `v7.3.4` (`7595a62d45ee1a2297eafa5f2ef5d0a45142d84d`) and Asahi `asahi-7.3.4-2` (`201be96df5654336bdcbe1da2103f193d7a0b940`). Asahi lists Wi-Fi support for the M1 MacBook Air upstream from Linux 6.1. The findings below come from the selected source trees. Linux runtime behavior on an A2337 remains unverified in this repository. [Stable release][stable], [Asahi tag][asahi], [M1 support table][m1]

## Binding and firmware gates

Both trees match Broadcom PCI Wi-Fi device `14e4:4425` and map BCM4378 chip revision 3 to `brcmfmac4378b1-pcie`. The J313 device tree supplies `apple,shikoku`. The driver's Apple firmware lookup considers board type, module information and antenna SKU. Its initialization also loads available country locale matrix (CLM) and TxCap files. The same PCI ID can select a different revision and firmware. [J313 device tree][j313], [PCI devices][pcidev], [Upstream revision map][up-pcie], [Asahi revision map][asahi-pcie], [Apple firmware lookup][lookup], [CLM and TxCap][blobs]

Firmware responses and driver policy shape the advertised bands, channels and interface combinations. For example, P2P modes depend on the P2P feature. Multiple-channel combinations depend on simultaneous dual-band (RSDB) or P2P multichannel (MCHAN) support. Both trees advertise DFS offload when a 5 GHz band is present and the firmware reports the `802.11h` feature. The actual feature flags on this board remain unverified. [Upstream feature detection][up-feat], [Asahi feature detection][asahi-feat], [Interface combinations][ifmodes], [DFS offload][dfs], [Channel flags][channel-flags]

The radar and passive channel designations come from the firmware's per-channel reply. [DFS flags and macOS proxy trace](dfs-proxy-policy.md#linux-and-asahi-policy)

The interface-combination code calculates separate limits for channels and infrastructure stations. [Dual-band policy report](simultaneous-dual-band.md#linux-advertisement-rules)

The pinned Asahi PCIe driver doubles the host-allocated receive ring depths and exposes the same `msgbuf_stats` readout on debug builds. [Queue and ring sizing](pcie-queue-sizing.md#linux-and-asahi)

## Standard controls and readouts

| Surface | What the pinned driver sources establish | Read-only bench query |
| --- | --- | --- |
| Signal and station counters | Both trees can report RSSI and average/per-chain values when firmware supplies them. They condition packet counts and transmit failures on firmware station statistics, and byte counts on structure version 4 or newer. The connected station has a fallback to a single RSSI reading when per-chain values are missing. [Upstream station reply][up-sta], [Asahi station reply][asahi-sta] | `iw dev "$IFACE" station dump` |
| PHY rates and rate selection | Upstream reports numeric Tx/Rx rates through the legacy rate field. Asahi can decode last-packet bandwidth, modulation and coding scheme (MCS), spatial stream count and guard interval from suitably populated version 7+ replies. For shorter version 7+ replies it attempts a Tx-rate fallback. Neither driver's operation table provides the standard bitrate-mask callback. `nl80211` returns `EOPNOTSUPP` without it. [Upstream rates][up-rates], [Asahi rate decoding][asahi-decode], [Asahi reply selection][asahi-rate-select], [Upstream operations][up-ops], [Asahi operations][asahi-ops], [Bitrate-mask dispatch][rate-dispatch] | `iw dev "$IFACE" station dump` |
| Current channel and width | Both drivers decode the firmware's current channel specification. A managed connection can use a channel hint when joining. AP startup takes a requested channel definition subject to role, availability and regulatory checks. A generic channel-setting request has no managed-station case. [Upstream channel report][up-channel], [Asahi channel report][asahi-channel], [Station join hint][join-hint], [AP startup][start-ap], [Channel dispatch][channel-dispatch] | `iw dev "$IFACE" info`, `iw phy "$PHY" info` |
| Power-save policy | Both drivers can defer application until the interface is up. Then they request fast power save or off, with P2P clients kept off, and send a separate inactivity timeout capped at 2,000 ms. The `nl80211` getter returns the kernel's stored preference. Actual radio sleep and energy use require separate observation. [Timeout and return path](radio-power-scheduling.md#linux-power-save-control), [Upstream policy][up-ps], [Asahi policy][asahi-ps], [Netlink getter and setter][ps-dispatch] | `iw dev "$IFACE" get power_save` |
| Transmit-power policy | Both drivers accept automatic, limited and fixed request types. Limited and fixed share one firmware request path. Requests use mBm (100 mBm per dBm). The getter reports the firmware power value converted from quarter-dBm to whole dBm on an up interface. This is a driver readback. Conducted power and EIRP require separate RF measurements. [Upstream power methods][up-power], [Asahi power methods][asahi-power], [Netlink interface report][iface-report], [Netlink power units][power-units] | `iw dev "$IFACE" info` |

Both trees register a survey callback behind the OBSS measurement capability. The callback rejects a connecting or connected primary interface and retunes the test radio for an 80 ms measurement. Busy and receive durations use different sums, and a failed PHY-noise query produces a fallback value. [Survey field definitions and effects](cca-provenance.md#linux-survey-behavior), [Upstream survey][up-survey], [Asahi survey][asahi-survey], [Asahi registration gate][survey-gate]

Both trees support the standard short and long retry-limit attributes on an up interface. Their shared handler can stop after the first successful update in a combined request. [Compiled source test and readback trace](wifi-retries-and-aggregation.md#linux-and-asahi-retry-controls)

The pinned Asahi driver stores antenna counts in the Linux availability bitmap fields. A two-chain firmware mask of `0x3` becomes `0x2` in those fields. The two driver operation tables have no antenna selection callback. [Antenna fields and test scope](radio-chain-policy.md#interpreting-linux-antenna-fields)

## Wi-Fi 6 capability evidence

Upstream stable `v7.3.4` builds HT and VHT band capability data. Asahi also queries whether HE (802.11ax) is enabled and constructs HE data for station mode. Its shared HE table sets some bits directly, including the 5 GHz 160 MHz, target wake time (TWT), and beamforming flags. The driver's per-channel permissions come from a separate firmware channel list. A 6 GHz band is added only if the firmware returns that band. Asahi's HE flags and generic decoder coverage alone leave BCM4378 support for individual features unverified. The A2337's [model-specific spectrum evidence](spectrum-sensing.md) covers 2.4 GHz HE20 and 5 GHz through HE80. [Upstream band setup][up-bands], [Asahi HE query][he-query], [Asahi HE table][he-table], [Channel flags][channel-flags], [Asahi band list][asahi-bands]

The 13 November 2026 `wireless-next` submission adapts Asahi's HE and 6 GHz work. Its reported 6 GHz connection was on an M3 Mac with BCM4388. It provides a runtime result for that device. [Patch cover letter][six-ghz]

## Bench acceptance criteria

1. Use a separate owned A2337 with console or Ethernet management and an owned AP on a permitted channel. Record board revision, `uname -r`, the installed kernel package and `ethtool -i "$IFACE"` driver and firmware versions. Keep SSID, BSSID and MAC addresses out of retained results. [Driver version fields][driver-info], [Asahi vendor firmware handling][asahi-firmware]
2. Capture the queries above and `iw reg get` with the station associated. Record which fields appear, their values, and any errors. Treat `iw phy` as an advertised-capability inventory. For an observed HE80 link, retain the station rate fields and operating channel/width and corroborate the link mode from the owned AP. [Linux Wireless `iw` documentation][iw], [Interface queries][iw-info]
3. For a separate test of power-save behavior, retain the policy readback and compare repeated idle energy or latency measurements on the same AP under otherwise similar conditions. For an RF power claim, record band, width and operating conditions alongside a calibrated measurement. Report accepted requests, getter values and independently measured effects as distinct observations.

[stable]: https://kernel.org/pub/linux/kernel/v7.x/
[asahi]: https://github.com/AsahiLinux/linux/releases/tag/asahi-7.3.4-2
[m1]: https://asahilinux.org/docs/platform/feature-support/m1/#m1-devices
[j313]: https://github.com/gregkh/linux/blob/v7.3.4/arch/arm64/boot/dts/apple/t8103-j313.dts#L16-L40
[pcidev]: https://github.com/gregkh/linux/blob/v7.3.4/arch/arm64/boot/dts/apple/t8103-jxxx.dtsi#L206-L221
[up-pcie]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L104-L116
[asahi-pcie]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L106-L118
[lookup]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L2267-L2303
[blobs]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/common.c#L175-L221
[up-feat]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/feature.c#L228-L251
[asahi-feat]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/feature.c#L311-L358
[ifmodes]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7689-L7756
[dfs]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L8006-L8008
[channel-flags]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7046-L7127
[up-sta]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L3200-L3262
[asahi-sta]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L3041-L3104
[up-rates]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L3209-L3218
[asahi-decode]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L2918-L2980
[asahi-rate-select]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L3105-L3127
[up-ops]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L6003-L6064
[asahi-ops]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L5906-L5967
[rate-dispatch]: https://github.com/gregkh/linux/blob/v7.3.4/net/wireless/nl80211.c#L14704-L14722
[up-channel]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L5735-L5797
[asahi-channel]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L5613-L5678
[join-hint]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L2381-L2455
[start-ap]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L5004-L5029
[channel-dispatch]: https://github.com/gregkh/linux/blob/v7.3.4/net/wireless/nl80211.c#L4105-L4207
[up-ps]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L3305-L3354
[asahi-ps]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L3166-L3214
[ps-dispatch]: https://github.com/gregkh/linux/blob/v7.3.4/net/wireless/nl80211.c#L14969-L15032
[up-power]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L2659-L2734
[asahi-power]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L2395-L2470
[iface-report]: https://github.com/gregkh/linux/blob/v7.3.4/net/wireless/nl80211.c#L4694-L4712
[power-units]: https://github.com/gregkh/linux/blob/v7.3.4/include/uapi/linux/nl80211.h#L2076-L2085
[up-survey]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L8166-L8247
[asahi-survey]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L8380-L8460
[survey-gate]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L8635-L8640
[up-bands]: https://github.com/gregkh/linux/blob/v7.3.4/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7346-L7414
[he-query]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7518-L7536
[he-table]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7378-L7475
[asahi-bands]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7945-L8008
[six-ghz]: https://lore-kernel.gnuweeb.org/linux-wireless/20261113-6ghz-v1-0-0b9a67e413a9@gmail.com/
[driver-info]: https://github.com/AsahiLinux/linux/blob/asahi-7.3.4-2/drivers/net/wireless/broadcom/brcm80211/brcmfmac/core.c#L570-L587
[asahi-firmware]: https://asahilinux.org/docs/platform/quirks/
[iw]: https://wireless.docs.kernel.org/en/latest/en/users/documentation/iw.html
[iw-info]: https://wireless.docs.kernel.org/en/latest/en/users/documentation/iw/replace-iwconfig.html#getting-info-on-wlan0
