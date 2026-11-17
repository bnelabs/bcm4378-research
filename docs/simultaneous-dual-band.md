# BCM4378 simultaneous dual-band policy

The A2337 lab sample transmitted on 2.4 and 5 GHz together in HT20 diversity modes. The installed macOS driver has separate logic for firmware capability discovery, cached dual-band information, and transmit policy. The following checks used the signed driver on build 26B131 and read the active device's published properties. [TÜV SÜD simultaneous transmission exhibit](https://fccid.io/BCGA2337/Test-Report/Simultaneous-transmission-report-4983630.pdf#page=7), [Local evidence](../evidence/2026-11-17-sdb-policy.json)

## Factory band assignment

The 250 installed BCM4378 profile names in the B1 and B3 directories resolve to ten distinct NVRAM payloads. All ten use the same band masks, including the Shikoku profile requested on the research Mac. The RF switch tables and coexistence entries for both transmit paths follow the same pairing. The A2337 test report's diversity modes use two transmit paths on each band. [Profile and instruction evidence](../evidence/2026-11-17-d11-band-assignment.json), [A2337 RF measurements](a2337-rf-tests.md#simultaneous-transmission)

| D11 unit | Profile key | Value | Configured RF band | RF switch table key |
| --- | --- | ---: | --- | --- |
| 0 | `bandcap` | `0x2` | 5 GHz | `swctrlmap_5g` |
| 1 | `slice/1/bandcap` | `0x1` | 2.4 GHz | `slice/1/swctrlmap_2g` |

Honshu, Capri, and Kyushu copy `slice/1/` into the D11 context when the attach path sees more than one slice and unit 1. They pass the prefix through the shared PHY settings into radio setup. The radio setup calls a resident firmware helper with the PHY context, `bandcap`, and the literal `3`. It saves the returned mask as a byte and prints bit 0 under `2G` and bit 1 under `5G`. Rizin and LLVM agree on the bit instructions in all three files. The helper body lies outside the mapped upload. [Prefix and mask instructions](../evidence/2026-11-17-d11-band-assignment.json), [D11 unit and program selection](firmware-layout.md#d11-microcode-and-core-selection)

Two 5 GHz channels fall under unit 0 in the factory map and two 2.4 GHz channels under unit 1. The firmware's scheduling of a same-band workload requires a measurement. A 5 GHz router leg and a 2.4 GHz peer leg are the combination that the stock profiles provision on separate units. Actual role placement and transmission overlap still require a radio bench measurement. [Signed policy and lab scope](#keeping-an-internet-link-while-using-another-channel)

The inspector lists each program hash alongside the band masks from the supplied board file.

```sh
python3 -B tools/inspect_d11_microcode.py \
  /usr/share/firmware/wifi/C-4378__s-B1/shikoku.trx \
  --board-profile /usr/share/firmware/wifi/C-4378__s-B1/P-shikoku-X3_M-RASP_V-m__m-6.11.txt
```

## Keeping an internet link while using another channel

The hardware lab result establishes simultaneous use of the two bands under the test modes. On this Mac, the running release advertises real simultaneous dual band (`rsdb`), and `en0` is the only router association observed. Both signed slices check that feature before reading the radio's band and slice capabilities. CoreWLAN exposes discovery scans, and the driver catalog has off-channel scan durations. A short, driver-scheduled scan and a sustained measurement on another channel ask different things of the radio. The latter, and two ordinary router associations on the same chip, remain unverified with the active stock build. [Apple scan API](https://developer.apple.com/documentation/corewlan/cwinterface/scanfornetworks%28withname%3Aincludehidden%3A%29), [Scan diagnostics](wifi-roaming.md), [Live firmware words](../evidence/2026-11-17-threadx-firmware.json)

Apple's AWDL peer interface is a separate role on the same chip. Apps can opt into it for direct transfers with a compatible peer. A measured transfer on a different band while routing over `en0` still needs an owned peer and synchronized observation on both bands. A second physical radio or test device can handle continuous probing or a second router association independently of the Mac's internet radio. [Apple peer networking](https://developer.apple.com/documentation/technotes/tn3151-choosing-the-right-networking-api#Peer-to-peer-networking), [Observed interface roles](driver-interfaces.md#running-wi-fi-interfaces)

The paired inspection tool measures a preview stream on `awdl0` and an archive stream on the infrastructure interface when both roles are available. Its per-connection report verifies where the payload traveled. A separate receiver on each band can measure frequency and airtime while the tool runs. [Two-device experiment](practical-radio-applications.md#test-the-direct-link-while-the-archive-is-moving)

## Read the channel history of each slice

On macOS 26B131 an ordinary user process read 66 reports from the running WLAN driver. They included destination channel counts, reasons for switching channels, transmit and receive bytes for both slices, and the AWDL schedule state. Each report in the `Channels Visited` group has an ID whose low 16 bits hold the firmware's channel specification and whose high byte holds the slice index. All 42 IDs returned by the sampler matched the published I/O Registry legend. The low channel byte normally gives the center channel. For example, `0xe12a` describes the 80 MHz group centered on channel 42 with primary 40. [Sampler and readout](live-wifi-airtime.md#read-channel-switch-reports), [Native evidence](../evidence/2026-11-17-channel-switch-reports.json), [Broadcom channel encoding](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/include/brcmu_d11.h#L579-L637)

Both signed driver slices dispatch 20-, 24- and 28-byte channel-switch records. The two longer layouts supply the slice index at offset `0x14`. For the 20-byte layout the driver uses slice 0 if the `rsdb` bit is clear. With the bit set it classifies a 2.4 GHz destination as slice 1 and other destinations as slice 0. The reporting routine adds one to the destination counter using the low 16 bits of the field at offset `0x08`. The aggregate includes both sources of slice attribution. [Signed parser and reporter instructions](../evidence/2026-11-17-channel-switch-reports.json)

| Reported slice | Cumulative switch reports | Destination history | Tx / Rx bytes added in the 60 s sample |
| --- | ---: | --- | ---: |
| 0 | 172,372 | 25 distinct 20 MHz channels and three 80 MHz specifications at 5 GHz | 506,048 / 1,571,811 |
| 1 | 3,174 | All 13 2.4 GHz channels plus 510 channel-zero entries | 0 / 0 |

In the slice 1 history, the most frequent real channel labels were 6, 1 and 11, with 773, 642 and 571 destination records respectively. Slice 1 also held 1,935 records labeled `Scan`. The reason totals and destination counts are independent aggregates. A channel-zero entry has a zero channel number in the firmware specification and supplies no usable frequency. The slice 0 history contains six records naming channel 144 at 20 MHz. CoreWLAN's current `TR` list excludes 144. The history has no timestamp or country for those six records. [Complete counts and current channel list](../evidence/2026-11-17-channel-switch-reports.json), [Regional channel rules](clm-channel-tables.md)

All 25 link samples reported `en0` on 5 GHz primary 40 at 80 MHz and all default IPv4 route checks returned `en0`. The host interface's packet counters advanced in every interval. The channel-switch and reason counters had zero deltas on both slices, and the `awdl0` packet counters had zero delta. The AWDL schedule accumulated time in the state labeled `InfraPri` with zero new state entries. The separate AWDL `SDB` value was zero with the same snapshot timestamp throughout. The sample verifies a live read of slice 0 traffic and a cumulative history on both slices. Concurrent use of both bands for a peer transfer remains a separate measurement. [Timed observations](../evidence/2026-11-17-channel-switch-reports.json)

### Time on a channel and time to retune

The driver records `Dwell Time` in milliseconds and `Phy Switch Time` in microseconds. Both signed slices tally the dwell field at offset `0x10`. The 28-byte record also has a hardware retune field at `0x18`. The signed driver passes the two fields to separate histograms. An ordinary user process read all four histograms, two per slice. [Instruction and runtime evidence](../evidence/2026-11-17-channel-switch-timing.json), [Apple's unit definitions](https://github.com/apple-oss-distributions/xnu/blob/main/iokit/IOKit/IOReportTypes.h)

The cumulative 5 GHz retune histogram held 172,040 values. All but one were at or below 1.5 ms, with the single value above that threshold at 1.501 ms. The corresponding dwell histogram held 69,496 records between 449 and 475 ms. Dwell records include time accrued before the switch. A benchmark needs the destination and purpose of the switch to relate dwell to a delay in network traffic. [Native histogram buckets](../evidence/2026-11-17-channel-switch-timing.json)

### 2.4 GHz records during 5 GHz traffic

In a separate 90-second passive run, all 31 snapshots reported the 5 GHz association on channel 40 at 80 MHz and the default route on `en0`. In one 3.008-second interval slice 1 added four destination records, one each for channels 1, 6 and 11 on 2.4 GHz and one for channel zero. Two reason records were labeled `Scan` and two `WLC Init`. The same interval saw 19 transmitted and 20 received packets on `en0`, with zero packet change on `awdl0`. The history groups observations inside the window. Pairing reasons with specific destinations and measuring actual airtime overlap still require synchronized observations. [Interval and adjacent snapshots](../evidence/2026-11-17-channel-switch-timing.json)

Three new dwell values totaled 347 ms in the 64–128 ms bucket. The fourth reported 483,079 ms in the open-ended top bucket, longer than the entire sampling window. The two new hardware retune values were both zero. The zero values' meaning remains open. [Per-bucket changes](../evidence/2026-11-17-channel-switch-timing.json), [Summary commands](live-wifi-airtime.md#read-channel-switch-reports)

## macOS firmware and platform gates

Both signed driver slices search the firmware's capability response for the word `rsdb` and set or clear the bit read by `checkForSDBSupport`. That bit gates `querySDBPolicies`. Its four reads handle version, capabilities, bands, and configuration, with response checks in each path. The capability handler caches fields that the AWDL-facing getter copies to its caller. A separate chip check uses the cached slice count and per-slice bytes. [Host instruction trace](../evidence/2026-11-17-sdb-policy.json)

Both driver slices format an `SDB Capabilities` diagnostic after successful replies. It reports the SDB flag, core count, current mode, and the same three values for each slice in this order. The last value is printed in hex and its subfields remain to be decoded. The inspection app selects a peer interface through Apple's networking API. The driver and firmware choose the radio channel. [Signed log field trace](../evidence/2026-11-17-d11-band-assignment.json), [Apple peer-to-peer API](https://developer.apple.com/documentation/network/nwparameters/includepeertopeer)

| Printed value for each slice | Source | Byte offsets from the start of the response buffer, slices 0 and 1 |
| --- | --- | --- |
| Band code | Bands response, signed byte | `0x0e`, `0x0f` |
| Capability byte | Capabilities response, unsigned byte | `0x10`, `0x11` |
| Configuration word | Configuration response, 32-bit value | `0x10`, `0x14` |

A 20-minute search of retained macOS logs with info and debug records included returned zero SDB summaries and zero firmware `RF Band Cap` records. The before-and-after stock reads showed `en0` still associated on 5 GHz, primary 40 at 80 MHz, with `rsdb` advertised. A saved driver summary from a separate bench could cross-check the reported slice values against the factory profile and the frequency observed in the air. [Read-only host observations](../evidence/2026-11-17-d11-band-assignment.json)

There are 56 macOS platform plists in the installed bundle. Each contains zero bytes in `wlan.sdb.profile`. The PCIe service on the running Mac publishes the same zero-byte value. A separate `wlan.txsdb.mode` integer maps to static transmit policy at value 1 and dynamic policy at value 2. The platform routine clears both flags before reading settings. Twelve plists specify value 1. The six BCM4378 board plists, including Shikoku, omit this integer. The scoped registry search also found zero copies of the integer. A later read of `AppleBCMWLANCore.FWCap` confirmed that the running firmware reported `rsdb`. The current transmit-policy flags, cached slice capabilities and simultaneous airtime remain unmeasured. [Platform inventory and registry sample](../evidence/2026-11-17-sdb-policy.json), [Published firmware capability words](../evidence/2026-11-17-live-firmware-capabilities.json)

All three distinct BCM4378 firmware images contain code references to `rsdb` and `rsdb_mode`. Each name has one aligned pointer and one PC-relative load in the reference image mapping, confirmed with Rizin. The scan of ten distinct stock NVRAM payloads found zero keys containing `sdb`, `rsdb`, `dbdc`, or `mchan`. A retained log search in the first four minutes after boot returned zero matching capability summaries. The full-boot search timed out. [Firmware and retained-log evidence](../evidence/2026-11-17-sdb-policy.json), [Reference load model](firmware-layout.md#reference-loading-model)

## Linux advertisement rules

The pinned Linux stable and Asahi drivers probe the firmware integer named `rsdb_mode`. Their helper enables the capability bit whenever the query status differs from the firmware's designated unsupported error. It ignores the returned integer for that decision. The main interface combination uses separate conditions for channel count and infrastructure station count. [Stable feature probe](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/feature.c#L185-L203), [Stable firmware variables](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/feature.c#L304-L344), [Asahi combinations](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7695-L7759), [Stable combinations](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7503-L7568)

| Feature flags | Maximum reported channels | Infrastructure station limit in the main combination |
| --- | ---: | ---: |
| RSDB clear and either P2P or MCHAN clear | 1 | 1 |
| RSDB set and either P2P or MCHAN clear | 2 | 1 |
| P2P and MCHAN both set | 2 | 2 |

These limits describe what the driver advertises. Concurrent associations and overlapping airtime require runtime measurements. On a separately managed A2337, pair the advertised `iw phy` combination with the actual interface roles and channel assignments. To check simultaneous transmission, compare the two legs on band-specific receivers with a shared time reference. Host counters can corroborate that traffic reached both interfaces. [All eight source-derived flag cases](../evidence/2026-11-17-sdb-policy.json), [Existing bench checks](asahi-controls.md#bench-acceptance-criteria)
