# BCM4378 clear-channel assessment reporting

The running `IO80211ReporterProxy` marked its registry legend public. The sample contained 602 legend rows and 2,761 channel entries across all groups. Within that metadata, the CCA last-reported and state groups each listed **38 channel numbers**. The public CoreWLAN getter listed **37 primary 20 MHz channels**. All appeared in both CCA groups, which also include channel 144 at 5,720 MHz. Noise labels were present for channel 40, the primary channel of the active 80 MHz association. Legend entries describe the available reports. The sample establishes label presence and leaves the reported values, measurement times, and channel 144 operation unverified. [Registry and association evidence](../evidence/2026-11-17-cca-provenance.json), [Apple DriverKit legend API](https://developer.apple.com/documentation/driverkit/ioreporter/createlegend), [Stock channel-plan comparison](spectrum-sensing.md#match-to-the-stock-channel-list)

The `en0` and `awdl0` groups each have average, IBSS, OBSS, and interference CCA report labels. The legend also lists `CCA (%) excluding own traffic` under link-quality measurements and a QBSS channel-utilization field under `en0`. The DriverKit image associates the QBSS label with its separate `setInterfaceQBSS` updater. [Registry labels and code references](../evidence/2026-11-17-cca-provenance.json)

The signed driver also has a feature-gated hardware mitigation request and can log an available channel specification from its overlapping-network event. The `obss_hw` capability word is absent from the current legacy response. [BSS coloring and spatial reuse](spatial-reuse.md)

## Native event and cache path

The signed macOS driver handles firmware channel-quality events. On its simple path, the associated-link routine computes an integer percentage from congestion and duration and writes it into the current BSS cache. Both examined driver slices also decode extended reports with self, other, and interference durations across total, wake, and sleep windows. The extended total adds the three categories before dividing by duration. For subsequent host event posting, both paths check an elapsed-time threshold of five seconds. This threshold governs host event posting. Firmware measurement duration and event cadence remain unobserved. [Host instruction trace](../evidence/2026-11-17-cca-provenance.json)

In the installed IO80211DriverKit image, the controller forwards CCA updates to the channel monitor. The monitor's `setChanCCA` routine registers the `CCA Last Reported` and `CCA State` legends. Separately, the current-link getter delegates to `IO80211BSSBeacon::getCCA`, which returns one cached byte when its validity flag is set. All three distinct BCM4378 firmware files have a decoded Thumb reference to the `cca_stats` literal under the reference load model. These traces establish the event and cache paths and the label registration mechanism. The legend alone leaves the source and time of any particular channel entry unverified. [DriverKit and firmware evidence](../evidence/2026-11-17-cca-provenance.json), [Reference firmware mapping](firmware-layout.md#reference-loading-model)

## IOReport catalog and sample path

On build 26B131, an unprivileged process used `IOReportCopyChannelsForDriver` to read all 2,761 descriptors for the same WLAN publisher. The 38 `CCA Last Reported` descriptors are simple integer reports. The 38 `CCA State` descriptors are state reports. The `en0` average and QBSS fields are also simple reports. The catalog library reads I/O Registry properties and builds channel descriptors. [Live catalog evidence](../evidence/2026-11-17-ioreport-access.json), [IOReport format definitions](https://github.com/apple-oss-distributions/xnu/blob/main/iokit/IOKit/IOReportTypes.h#L75-L106)

The channel monitor creates four states per channel. Its comparisons assign valid integer percentages to the following ranges. The state format accumulates ticks in each state. With a common timebase and continuous counters, differences between two snapshots of the same channel give the time spent in each range over the intervening period. [State labels and boundaries](../evidence/2026-11-17-ioreport-access.json), [State report fields](https://github.com/apple-oss-distributions/xnu/blob/main/iokit/IOKit/IOReportTypes.h#L98-L107)

| State label | CCA input |
| --- | ---: |
| `00  25` | 0–24% |
| `25  50` | 25–49% |
| `50  75` | 50–74% |
| `75 100` | 75–100% |

`IOReportCreateSamples` requests a kernel report update. The live reporter proxy belongs to `AppleBCMWLANCore`. Its update dispatch resolves to the core's override in both installed driver slices. When the core accepts commands, its gated path dispatches power statistics and diagnostics before the report collectors. The inspected paths include firmware power-duration reads and conditional event-counter enable and disable calls. The active-Mac test covered catalog access. Sample values and the effects of the full update path remain open for a separately managed device. [Sample path evidence](../evidence/2026-11-17-ioreport-access.json), [DriverKit report update dispatch](https://github.com/apple-oss-distributions/xnu/blob/main/iokit/Kernel/IOUserServer.cpp#L313-L342)

## Linux survey behavior

The pinned Linux stable and Asahi survey callbacks are byte-identical. Both select the primary interface for the association-state check, return busy while that interface is connecting or connected, and select the requested channel when the survey proceeds. The callback brings the interface up, queries PHY noise, and requests an **80 ms** firmware measurement. It waits **90 ms** before collecting results. The channel-set failure path leaves the result fields empty. The exit path performs power-policy cleanup and leaves subsequent channel selection to other driver operations. [Stable survey callback](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L8166-L8263), [Asahi survey callback](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L8380-L8477)

The busy value is the nominal survey duration minus parsed idle time. The receive field sums OBSS, IBSS, no-category, and no-packet durations. It can therefore include time outside decoded packet receptions. The transmit field comes from the parsed TX duration. A failed PHY-noise query produces a fallback of **−80 dBm**, which is also a plausible measurement. Readings at that value need the driver error context. The survey is a time-domain occupancy measurement. Interferer identification and spectral shape need independent RF observations. [Stable survey constants](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L88-L101), [OBSS parser](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L8039-L8107), [Linux survey fields](https://docs.kernel.org/next/driver-api/80211/cfg80211.html)

## Reproduce the read-only inventory

```sh
python3 tools/read_cca_legend.py
swift tools/read_wifi_status.swift
```

The inventory emits channel numbers, selected labels, and aggregate counts. The existing native status investigation identifies a CCA status field behind the root-gated diagnostic command. A test on a separately managed device can compare actual CCA and QBSS values with a synchronized RF receiver. The Linux survey belongs on that independently managed radio because it changes channels. [Registry reader](../tools/read_cca_legend.py), [Native station status](live-access.md#station-diagnostic-fields)

The catalog reader uses the `libIOReport` signatures verified on this system. It reports publisher-matched count and format metadata. [Catalog reader](../tools/read_ioreport_catalog.c)

```sh
catalog_dir="$(mktemp -d)"
xcrun clang -Wall -Wextra -Werror -framework CoreFoundation -framework IOKit \
  -lIOReport tools/read_ioreport_catalog.c -o "$catalog_dir/read_ioreport_catalog"
"$catalog_dir/read_ioreport_catalog"
```
