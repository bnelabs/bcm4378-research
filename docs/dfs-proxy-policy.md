# BCM4378 DFS proxy and channel switches

The running Shikoku firmware advertises `dfsp`, and the live PCIe service supplies the board property checked by the signed driver's DFS proxy gate. At sampling time the Mac was associated on channel 40 at 80 MHz. A DFS proxy session and a DFS channel change on this build remain unmeasured. [Host and driver evidence](../evidence/2026-11-17-dfs-proxy-policy.json)

## Board and firmware inputs

`wlan.dfsproxy.enabled` is eight zero bytes in all 56 macOS platform profiles in each installed directory and in the live `AppleBCMWLANBusInterfacePCIe` service. In both driver slices, the config manager sets its permission after acquiring readable backing bytes from the Data property. The eight-byte value satisfies that check. In the installed DriverKit cache the helper tests the returned data pointer. The permission therefore comes from the Data's presence and readability. [Property inventory and gate](../evidence/2026-11-17-dfs-proxy-policy.json)

Both `IssueFwCap` implementations look for the complete word `dfsp` and check the board permission. They set internal feature bit 54 when both inputs pass and clear it otherwise. The live registry provides both inputs. The effective peer-session mode requires a separate measurement. [Legacy capability provenance](firmware-capabilities.md), [Shikoku gate trace](../evidence/2026-11-17-dfs-proxy-policy.json)

## Peer eligibility and channel classification

The installed IO80211DriverKit cache has an AWDL eligibility routine that checks peer DFS-proxy support and considers local and remote infrastructure channels. Its data path uses DFS channel classification and a shared proxy-availability check. The shared NAN path also calls the availability check. These are static call paths in the shipped framework. The current sample establishes the AWDL reporter's presence. [Framework call relationships](../evidence/2026-11-17-dfs-proxy-policy.json)

The AWDL schedule-state path can call `enableDFSProxyMode`, which configures proxy mode and related channel-switch-announcement handling for the peer. In both AppleBCMWLAN slices the proximity interface has internal firmware paths for `awdl_dfsp_cfg` and `awdl_dfsp_ucsa`. It has separate diagnostic branches for suspect and resume events. In the shared cache, `reportDataPathEvents` reaches the DFS proxy manager's suspend and resume handlers. [Signed driver and shared cache trace](../evidence/2026-11-17-dfs-proxy-policy.json)

The driver populates its per-channel data in `handleChanInfoTimer`. It takes bit 3 of the firmware's `per_chan_info` result and stores it in the array read by `isDFSChannel`. The lookup matches channel and band before returning the cached radar designation. At sampling time CoreWLAN listed 15, 14 and 12 primary channel identifiers at 20, 40 and 80 MHz respectively within the A2337 filing's main DFS channel groups. These counts apply to the station-mode channel list. [Channel cache and inventory](../evidence/2026-11-17-dfs-proxy-policy.json), [A2337 channel blocks](spectrum-sensing.md#a2337-lab-spectrum)

## Published telemetry

The live `awdl0` legend exposes seven DFS-related labels. They cover cached peers on DFS, AirPlay connections and failures, channel-switch announcements (CSAs) received from a peer or an AP, suspected DFS issues, and resumed DFS. The infrastructure legend has a separate `Channel Switch Event` label for `en0`. General per-slice switch reasons include scans, station operation, association and synchronization. Both signed slices parse 20-, 24- and 28-byte channel-switch records through the per-slice reporting routines. [Exact labels and parser evidence](../evidence/2026-11-17-dfs-proxy-policy.json)

The read-only inventory reports this metadata under `wifi.dfs_proxy`. Values would need a separate capture. The IOReport update path can issue firmware requests, so value sampling belongs on a separately managed device. [Inventory reader](../tools/read_macos_inventory.py), [IOReport update trace](cca-provenance.md)

## A2337 conformance measurements

TÜV SÜD report 75949395-12 Issue 01 tested the A2337 in two 802.11ac VHT80 client scenarios under a coordinating master. It labels the test setups as clients without radar detection. The move interval and aggregate closing airtime describe different parts of the measured response. The report identifies the second setup as client-to-client. The application protocol and equivalence to stock AWDL operation remain unverified. [Infrastructure setup](https://device.report/m/e27c03bc861ebf56abc2119aff6d1ab85f56be8043aef432de943103e4ac7d69.pdf#page=179), [Client-to-client setup](https://device.report/m/e27c03bc861ebf56abc2119aff6d1ab85f56be8043aef432de943103e4ac7d69.pdf#page=183)

| Client setup | Channel move time | Aggregate closing airtime |
| --- | ---: | ---: |
| Infrastructure | 113.26 ms | 1.32 ms |
| Client-to-client | 29 ms | 14.86 ms |

[Infrastructure results](https://device.report/m/e27c03bc861ebf56abc2119aff6d1ab85f56be8043aef432de943103e4ac7d69.pdf#page=180), [Client-to-client results](https://device.report/m/e27c03bc861ebf56abc2119aff6d1ab85f56be8043aef432de943103e4ac7d69.pdf#page=184)

## Linux and Asahi policy

The pinned stable and Asahi drivers enable the advertised DFS offload feature when the device has a 5 GHz band and firmware feature discovery finds `802.11h`. Their channel setup assigns the kernel's radar and no-initiate-radiation flags when the firmware marks a channel for radar handling. A passive-only firmware flag also sets no-initiate-radiation. These paths establish the Linux representation of the firmware's channel policy. A running A2337 still needs its own observation. [Stable offload gate](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7789-L7795), [Asahi feature word](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/feature.c#L54-L62), [Asahi per-channel flags](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7114-L7129)

Each of the three distinct stock BCM4378 images contains `dfsp` and `802.11h` as literal words. The running macOS legacy reply includes `dfsp` and omits `802.11h`. The reply that Linux receives from the chip remains unmeasured. [Artifact and live capability evidence](../evidence/2026-11-17-dfs-proxy-policy.json)

## Measure peer continuity

Use a separately managed A2337, an owned AP, and an Apple TV on Ethernet to measure peer-to-peer AirPlay continuity during an ordinary AP-managed channel change. Record the AP's transition time, the client's channel readout, and the length of any playback gap. Correlate peer and AP CSA counters where available. For a DFS-specific result, use a retained legitimate DFS event or a qualified RF lab and record the actual channel and application recovery separately. Apple recommends Ethernet for the Apple TV when the infrastructure uses DFS and peer-to-peer AirPlay is desired. [Apple AirPlay deployment guidance](https://support.apple.com/en-gb/guide/deployment/-dep9151c4ace/web)

Run `python3 tools/read_macos_inventory.py` to reproduce the published board-property and legend observations. Run `swift tools/read_wifi_status.swift` to reproduce the current station-channel listing.
