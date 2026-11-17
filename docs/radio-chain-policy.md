# BCM4378 radio chains and channel-width policy

Apple specifies two spatial streams on both bands for the 2020 M1 MacBook Air. All ten distinct installed BCM4378 NVRAM payloads set `aa2g`, `aa5g`, `txchain` and `rxchain` to the two-bit mask `0x3`. The running Shikoku driver requested the X3 RASP profile. CoreWLAN reported a 5 GHz, 80 MHz Wi-Fi 6 association on `en0`. These observations record the provisioned masks and operating channel. The active chain masks and stream count of individual packets remain unmeasured. [Apple Wi-Fi specifications](https://support.apple.com/en-au/guide/deployment/-dep268652e6c/web), [Profile and host evidence](../evidence/2026-11-17-radio-chain-policy.json)

## Power-saving and width controls

Both signed macOS 27.2.1 driver slices check a firmware feature bit and a board configuration input for each path.

| Driver path | Board input | Bit and legacy capability word |
| --- | --- | --- |
| MIMO power save | Presence of `wlan.mimo_ps.enabled` | 44, `mimo_ps` |
| OCL | Presence of `wlan.ocl.enabled` | 47, `ocl` |
| Beacon-based channel-width switching | Numeric `wlan.psbw.enabled` property | 3, `psbw` |

Shikoku's live PCIe service publishes empty Data for the two presence-based settings. Both are present in all 56 profiles in each stock directory. The numeric width property and the separate `wlan.ocl_awdl.enabled` Data setting are absent from the stock Mac profiles and the live service. The published legacy reply omits `mimo_ps`, `ocl` and `psbw`. The driver can also set all three bits through `processFwFeatures` when it parses the separate extended capability reply. The effective flags and policy state remain open. [Board and capability trace](../evidence/2026-11-17-radio-chain-policy.json), [Capability reply provenance](firmware-capabilities.md)

The MIMO power manager has separate initialization, join, link-up, and associated-sleep paths. It uses `mimo_ps_cfg` for mode configuration, `mimo_ps_status` for status, and `pm_bcnrx` for beacon receive-chain policy. Its chain context combines `txchain`, `rxchain`, current channel specification and MIMO settings. The OCL setup path has separate enable and RSSI-threshold requests. The inspected setup passes a threshold argument of −70. Firmware acknowledgment and the resulting threshold remain unmeasured. [Driver trace](../evidence/2026-11-17-radio-chain-policy.json)

The associated-sleep entry and exit paths can invoke `configureBeaconBasedChannelWidthSwitch`. When the feature, association, and cached width checks pass, the helper requests a 20 MHz mode for entry and an 80 MHz mode for exit using `psbw_cfg`. The firmware's resulting width transitions remain unmeasured. [Width path](../evidence/2026-11-17-radio-chain-policy.json), [Associated-sleep trace](radio-power-scheduling.md)

## What the spatial-stream reporter measures

The public WLAN IOReport legend includes `NSS State` for `en0`. In the installed IO80211DriverKit cache, `getInfraLinkProperties` obtains a four-byte chain reply, counts the set bits in its second and third bytes, and passes the smaller count to `setMaxNSS` for the state reporter. On the AppleBCMWLAN fallback, the getter fills the four bytes from `hw_rxchain`, `hw_txchain`, `txchain`, and `rxchain`, in that order. The reported state on this path therefore uses the hardware and configured **transmit** masks. For example, masks `0x3` and `0x2` yield state 1. Establishing which chains carried a particular frame requires a separate observation. [Chain getter and cached reporter trace](../evidence/2026-11-17-radio-chain-policy.json)

The live legend also publishes 16 Operating Mode Indication (OMI) counters in each of `Chip`, `Slice 0` and `Slice 1`. They include request and successful-transmission counts for receive stream count, transmit space-time stream count, and channel-width changes. The two per-slice implementations read a 68-byte firmware counter record, take sixteen little-endian 32-bit values after the first four bytes, and publish each field with `setValue`. The evidence matches the field offsets to the live channel labels. The chip-level values and on-device event rates remain open. [IEEE 802.11ax OMI overview](https://iln.ieee.org/Public/ContentDetails.aspx?id=D7A143251D2F4B92BCC1D5B182292A78), [Counter field mapping](../evidence/2026-11-17-radio-chain-policy.json)

The inventory above reads published legend properties. The full IOReport update path can send commands to firmware. Collecting actual values belongs on a separately managed test device. [IOReport update trace](cca-provenance.md)

## Interpreting Linux antenna fields

The pinned Asahi driver queries `rxchain` and `txchain` and counts the set bits. It then puts those counts into `available_antennas_rx` and `available_antennas_tx`. Linux defines both fields as bitmaps and serializes the stored integers directly. A firmware mask of `0x3` therefore produces `0x2` in the available-antenna field on this Asahi code path. The driver falls back to count 1 if a query fails. Interpret those fields alongside the firmware response and the station's per-packet stream telemetry. [Asahi chain initialization](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7543-L7575), [Linux bitmap definitions](https://docs.kernel.org/driver-api/80211/cfg80211.html#c.wiphy), [Asahi netlink serialization](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/net/wireless/nl80211.c#L3149-L3154)

Both pinned brcmfmac operation tables omit the standard antenna getter and setter callbacks. The stable Linux driver queries the receive mask and uses its bit count to build capabilities. Asahi can report the last packet's bandwidth and spatial streams when the firmware supplies the appropriate statistics. [Stable chain initialization](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7372-L7413), [Linux and Asahi station readouts](asahi-controls.md#standard-controls-and-readouts)

## Verify chain use on a test link

On a separately managed A2337 and an owned AP, hold band, width and placement fixed. Record the link with both an idle interval and a sustained transfer in each direction. Pair the reported chain masks and per-chain RSSI with per-packet spatial-stream counts from compatible AP diagnostics or a passive capture of the test network. Use the OMI counters and over-the-air operating-mode indications to time reported stream or width changes. A comparison across matched conditions can help distinguish a persistent chain loss from a link that chooses one spatial stream for some frames. [Model-specific RF tests](a2337-rf-tests.md), [Signal and rate evidence](spectrum-sensing.md)

To reproduce the published properties on macOS, run `python3 tools/read_macos_inventory.py` from the repository root. The board inputs appear under `wifi.radio_power_config_properties`. The IOReport label lists appear under `wifi.radio_chain_reporting`.
