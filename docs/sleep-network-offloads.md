# BCM4378 sleep network offloads

The M1 MacBook Air's running Shikoku firmware advertises `arpoe`, `ndoe`, `pktfltr2`, `bdo`, `tko`, and `lpas`. The signed macOS 26B131 driver has separate paths for neighbor resolution, packet filtering, Bonjour service discovery, and established TCP connections. The live sample covers the awake host. The evidence file records the signed binary hash and the corresponding entry points in both slices. [Firmware capabilities](firmware-capabilities.md), [Snapshot and driver trace](../evidence/2026-11-17-sleep-network-offloads.json)

## Wake policy and the board declaration

| Surface | Observed on the A2337 | Scope |
| --- | --- | --- |
| `pmset` network wake `womp` | AC and live 1, battery 0 | macOS preference for waking to provide network access. Apple documents its use for shared resources. [Host power policy](host-power-policy.md), [Apple's network wake documentation](https://support.apple.com/en-gb/guide/mac-help/mh27905/mac) |
| `pmset` `tcpkeepalive` | 1 on both power profiles | Host policy for TCP keepalives during sleep. [Apple PowerManagement source](https://github.com/apple-oss-distributions/PowerManagement/blob/d415e45501842834a280930c3eed9186544a67f0/pmset/pmset.m#L5796-L5806) |
| `bcom.wow.magic-packet` | Boolean false on the live PCIe service and in Shikoku's plist | The 56 installed board plists in the driver bundle all set this property to false. The 56 shared firmware copies match by relative path and content. [Board audit](../evidence/2026-11-17-sleep-network-offloads.json) |
| `mDNS_Keepalive` | Boolean true on the primary Skywalk and low-latency services | Apple's published mDNSResponder 878.270.2 uses the presence of this key as an interface support test. The snapshot leaves downloaded records and occupied TCP slots unmeasured. [Apple mDNSResponder support check](https://github.com/apple-oss-distributions/mDNSResponder/blob/mDNSResponder-878.270.2/mDNSMacOSX/mDNSMacOSX.c#L3224-L3255), [Registry values](../evidence/2026-11-17-sleep-network-offloads.json) |

`gatherParameterData` looks up `bcom.wow.magic-packet` and stores the result in the field returned by `AppleBCMWLANConfigManager::wompEnabled`. `configurePktFilters` checks that getter before installing its built-in WOMP magic-packet filter. The function also has a separate path for its existing custom filter list. A board declaration and a macOS power preference describe different parts of the wake chain. Which packets can wake this Mac remains a measurement. [Driver trace](../evidence/2026-11-17-sleep-network-offloads.json)

## What the driver can hand to firmware

| Function | Driver path | Evidence still needed |
| --- | --- | --- |
| IPv4 address resolution | `configureARPOffload` sets `arpoe` and the `arp_ol` policy. The routine can clear and populate the firmware's IPv4 host-address list. | Firmware replies for the test station's own addresses during sleep. |
| IPv6 neighbor discovery | `configureNeighbourDiscovery` checks the `ndoe` feature in its table-clearing path, sets `ndoe`, and can populate the host IPv6 list with `configureHostIPsForNeighbourDiscovery`. | Which address types receive an answer and when the address list is refreshed. |
| Wake packet filters | `configurePktFilters` branches on `pktfltr2`. The enable and disable routines use `pkt_filter_enable`. `configureWoWExit` calls the filter teardown path. | Installed filters and wake reasons for actual sleep transitions. |
| Bonjour discovery | For firmware with the `bdo` feature, the driver can report NIC-proxy limits through the primary Skywalk interface, flatten Bonjour records, and transfer them through `bdo`. WoW entry checks that the config was downloaded before enabling this offload. The exit path can disable it. | Which DNS-SD records the NIC serves during sleep, and whether a separate sleep proxy handled a response. |
| Gratuitous ARP keepalive | `programGARP` has a separate `mkeep_alive` path. Its format-2 branch defaults the private retry-count input to five and clamps it to five. | Whether the stock policy schedules it on this device and how its announcements appear on the LAN. |

The ARP and IPv6 branches are reachable from the wake packet filter setup. The driver records `ndoe`, `pktfltr2`, `bdo`, and `tko` at legacy firmware feature indices 30, 31, 45, and 49. Associated-sleep permission and beacon wake timing have their own inputs. [Driver entry points](../evidence/2026-11-17-sleep-network-offloads.json), [Radio power and wake scheduling](radio-power-scheduling.md)

## TCP keepalive slots

The driver's eligibility check requires the firmware `tko` feature and the driver's TCP keepalive policy byte. `populatePlatformProperties` initializes that byte to one before checking the private `wlan.tcpka` input. During initialization the driver asks firmware for its capacity. A byte from a successful reply becomes the cached value behind `getMaxSupportedTCPSocketOffloads`. The compiled comparison with four controls diagnostic logging. The on-device slot count remains unmeasured. [Driver trace and observation](../evidence/2026-11-17-sleep-network-offloads.json)

The WoW entry path checks `bdo` and TCP keepalive eligibility before staging frames through `mDNSOffloadConfigureKeepAlives`. That routine uses the cached slot count and calls `setTCPAliveOffloadConfig` for selected frames. After successful staging, the entry path calls `setTCPAliveOffloadEnable`. The corresponding exit path asks for the TCP offload wake reason and disables the offload when eligible. Host policy, available slots, programmed flows, and probes sent during sleep each require their own evidence. [WoW entry and exit trace](../evidence/2026-11-17-sleep-network-offloads.json)

Applications can request TCP keepalive and set idle time, probe interval, and retry count with `NWProtocolTCP.Options`. The four properties type-checked with the macOS 27.2 SDK. An app-level request supplies a repeatable workload for testing which established flows the stock stack actually offloads. [Apple Network framework options](https://developer.apple.com/documentation/network/nwprotocoltcp/options)

## Keepalive wake reasons

Both signed driver slices parse an accepted TCP keepalive status reply with a little-endian 16-bit command value of `4`, a 16-bit payload length, a count byte, and one status byte per reported slot. They label the statuses below. The driver's cached reason getter translates raw codes 1 through 6 with the same table in both binaries. The WLAN report uses that result as its main reason for event subtype 151, the Broadcom TCP keepalive offload event. This gives a bench test a way to distinguish incoming data from timeout and TCP validation failures. [Signed instruction and table evidence](../evidence/2026-11-17-sleep-wake-attribution.json), [Broadcom event definition](https://github.com/StreamUnlimited/broadcom-bcmdhd-4359/blob/master/include/bcmevent.h#L2664)

| Raw per-slot status | Meaning | Mapped driver wake reason |
| ---: | --- | ---: |
| 0 | Normal | — |
| 1 | No reply to keepalive | 27 |
| 2 | TCP acknowledgment flag clear | 28 |
| 3 | Unexpected TCP flag | 30 |
| 4 | Invalid TCP acknowledgment number | 29 |
| 5 | Invalid TCP sequence number | 31 |
| 6 | Incoming TCP data | 26 |
| 255 | Unavailable | — |

The current registry sample published `LastWakeReason=0` on the WLAN stack. The status reply property `TKO status data` is behind the driver's diagnostic publication check and was absent from all 101 sampled registry entries. The published WLAN reporter legend had 602 rows with zero `WiFi Wake` matches. A live report of any decoded socket outcome still requires a separate test. [Registry sample and diagnostic path](../evidence/2026-11-17-sleep-wake-attribution.json)

For a saved binary `TKO status data` value from this driver family, the offline reader decodes each reported slot and keeps unknown codes visible. It checks the length and count before reading. Fixtures covered all eight recognized values, one unrecognized value, an empty slot list, and five malformed records. [Reader and test results](../tools/inspect_sleep_wake.py), [Fixture evidence](../evidence/2026-11-17-sleep-wake-attribution.json)

```sh
python3 -B tools/inspect_sleep_wake.py --tko-status "$saved_tko_status"
```

## Retained wake history

The Mac's saved `pmset` history included 156 `DarkWake` rows at the time of the sample. Of these, 67 used the shared Wi-Fi and Bluetooth tag `wifibt`. There were 45 on battery and 22 on AC. All 67 predated the current boot and had a system management controller claim at the same second with empty driver details. A search for the WLAN driver diagnostics from eight seconds before through 35 seconds after the three most recent tagged wakes returned zero records. The retained data locates those events at the platform level. The initiating radio and packet or offload remain unverified. [Aggregate history and log queries](../evidence/2026-11-17-sleep-wake-attribution.json), [Apple's claimed-wake formatter](https://github.com/apple-oss-distributions/PowerManagement/blob/d415e45501842834a280930c3eed9186544a67f0/pmset/pmset.m#L5987-L6013)

The 45 battery events had a median reported duration of six seconds. Apple calculates the `DarkWake` duration from the following sleep or full wake when a usable record is available. The duration measures time between host power transitions. RF-on time and energy require separate instrumentation. All 161 retained `Sleep` rows had `TCPKeepAlive=active`. Occupied slots and packet exchange remain unmeasured. [History summary](../evidence/2026-11-17-sleep-wake-attribution.json), [Apple's duration calculation](https://github.com/apple-oss-distributions/PowerManagement/blob/d415e45501842834a280930c3eed9186544a67f0/pmset/pmset.m#L6425-L6441)

The tool can summarize retained records or the current boot using `--boot-epoch`. It emits counts and duration summaries from the input. The current Mac stayed on the `en0` route during the reads. [Offline reader](../tools/inspect_sleep_wake.py), [Connectivity samples](../evidence/2026-11-17-sleep-wake-attribution.json)

```sh
boot_epoch=$(sysctl -n kern.boottime | sed -E 's/^\{ sec = ([0-9]+),.*/\1/')
pmset -g log | python3 -B tools/inspect_sleep_wake.py --pmset-log - --boot-epoch "$boot_epoch"
```

## Linux and Asahi comparison

Linux stable 7.3.4 and Asahi 7.3.4-2 derive the PCIe bus wake-support flag from the endpoint's PCI D3hot PME capability. With the bus flag set, the feature probe checks `wowl` and then `wowl_cap`. A successful `wowl_cap` query sets the driver's wake-compatible ARP and ND flag. Its other bits may advertise preferred-network detection and group-key rekey failure. [Linux PCIe probe](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L2514-L2524), [Asahi PCIe probe](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L2883-L2894), [Linux feature probe](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/feature.c#L306-L319), [Asahi feature probe](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/feature.c#L331-L344)

When the driver sets up WoWLAN without the wake-compatible ARP and ND flag, it disables ordinary ARP and ND offloads for that sleep interval and restores them on resume. Both versions describe magic-packet, disconnect, and pattern triggers in their wiphy template. The driver adds network detection and group-key failure triggers conditionally. The TCP wake-offload field is unset in both templates. On an Asahi bench, the registered wiphy capabilities are the starting comparison with macOS. [Linux resume and suspend](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L4179-L4251), [Linux wiphy template](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7619-L7655), [Asahi resume and suspend](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L4038-L4110), [Asahi wiphy template](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7811-L7847)

## Bench measurements and use cases

Use a second A2337 with console access, an owned AP, and a wired observer. Record the firmware identity, host preferences, association, and host sleep and dark-wake intervals. Capture at the AP or observer so that observation continues independently of the sleeping station.

1. **Keep a shared service discoverable.** Register a test Bonjour service and browse from the observer before, during, and after sleep. Record the DNS-SD answers, the responding device, and the first actual service access. Repeat with the documented network-wake setting changed on the bench machine. Time-correlate the responses with host wake events to tell when the host resumed. Record any AP or other device offering a sleep proxy.
2. **Keep an idle TCP session alive.** Start with one connection to the wired test peer using ordinary socket keepalive. Compare IPv4 and IPv6, then repeat with additional connections. Record probe intervals, which flows stay alive, and whether the host woke. Compare a genuine application request with loss of the test peer and look for the corresponding data and timeout reasons in retained diagnostics. Keep address-resolution observations separate by exercising ordinary ARP and IPv6 neighbor discovery independently. Identify the responder for each reply.
3. **Measure sleep energy and response time.** Run the same connection workload with and without socket keepalive. Keep the sleep duration and power conditions fixed. Compare energy, total host wake time, and the latency of the first request after sleep. The Somniloquy prototype measured similar trade-offs on its own NIC hardware. [Somniloquy research paper](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/agarwal-NSDI09-Somniloquy.pdf)

On the connected research Mac, `tools/read_macos_inventory.py` reads the published board and interface values. `pmset -g live`, `pmset -g custom`, and `pmset -g ps` reproduce the host preference sample. For the static trace, verify the installed dext's signature and hash, thin the Mach-O with `lipo`, and disassemble each slice with `llvm-objdump`. The evidence identifies the matching symbols and virtual addresses. [Inventory reader](../tools/read_macos_inventory.py), [Evidence](../evidence/2026-11-17-sleep-network-offloads.json)
