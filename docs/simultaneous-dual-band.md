# BCM4378 simultaneous dual-band policy

The A2337 lab sample transmitted on 2.4 and 5 GHz together in HT20 diversity modes. The installed macOS driver has separate logic for firmware capability discovery, cached dual-band information, and transmit policy. The following checks used the signed driver on build 26B131 and read the active device's published properties. [TÜV SÜD simultaneous transmission exhibit](https://fccid.io/BCGA2337/Test-Report/Simultaneous-transmission-report-4983630.pdf#page=7), [Local evidence](../evidence/2026-11-17-sdb-policy.json)

## macOS firmware and platform gates

Both signed driver slices search the firmware's capability response for the word `rsdb` and set or clear the bit read by `checkForSDBSupport`. That bit gates `querySDBPolicies`. Its four reads handle version, capabilities, bands, and configuration, with response checks in each path. The capability handler caches fields that the AWDL-facing getter copies to its caller. A separate chip check uses the cached slice count and per-slice bytes. [Host instruction trace](../evidence/2026-11-17-sdb-policy.json)

There are 56 macOS platform plists in the installed bundle. Each contains zero bytes in `wlan.sdb.profile`. The PCIe service on the running Mac publishes the same zero-byte value. A separate `wlan.txsdb.mode` integer maps to static transmit policy at value 1 and dynamic policy at value 2. The platform routine clears both flags before reading settings. Twelve plists specify value 1. The six BCM4378 board plists, including Shikoku, omit this integer. The scoped registry search also found zero copies of the integer. This establishes the bundled default and published properties. The current transmit-policy flags and firmware capability reply remain unobserved. [Platform inventory and registry sample](../evidence/2026-11-17-sdb-policy.json)

All three distinct BCM4378 firmware images contain code references to `rsdb` and `rsdb_mode`. Each name has one aligned pointer and one PC-relative load in the reference image mapping, confirmed with Rizin. The scan of ten distinct stock NVRAM payloads found zero keys containing `sdb`, `rsdb`, `dbdc`, or `mchan`. A retained log search in the first four minutes after boot returned zero matching capability summaries. The full-boot search timed out. [Firmware and retained-log evidence](../evidence/2026-11-17-sdb-policy.json), [Reference load model](firmware-layout.md#reference-loading-model)

## Linux advertisement rules

The pinned Linux stable and Asahi drivers probe the firmware integer named `rsdb_mode`. Their helper enables the capability bit whenever the query status differs from the firmware's designated unsupported error. It ignores the returned integer for that decision. The main interface combination uses separate conditions for channel count and infrastructure station count. [Stable feature probe](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/feature.c#L185-L203), [Stable firmware variables](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/feature.c#L304-L344), [Asahi combinations](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7695-L7759), [Stable combinations](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7503-L7568)

| Feature flags | Maximum reported channels | Infrastructure station limit in the main combination |
| --- | ---: | ---: |
| RSDB clear and either P2P or MCHAN clear | 1 | 1 |
| RSDB set and either P2P or MCHAN clear | 2 | 1 |
| P2P and MCHAN both set | 2 | 2 |

These limits describe what the driver advertises. Concurrent associations and overlapping airtime require runtime measurements. On a separately managed A2337, pair the advertised `iw phy` combination with the actual interface roles and channel assignments. To check simultaneous transmission, compare the two legs on band-specific receivers with a shared time reference. Host counters can corroborate that traffic reached both interfaces. [All eight source-derived flag cases](../evidence/2026-11-17-sdb-policy.json), [Existing bench checks](asahi-controls.md#bench-acceptance-criteria)
