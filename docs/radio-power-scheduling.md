# BCM4378 radio power and wake scheduling

The M1 Air's live firmware capability reply contains `he`, `lpas` and `dtim_miss`. CoreWLAN reports an 802.11ax association. The observations below use macOS 27.2.1 build 26B131, the two signed AppleBCMWLAN slices, and the three distinct installed BCM4378 firmware images. The Mac remained connected through `en0`. [Host, artifact, and capability evidence](../evidence/2026-11-17-radio-power-scheduling.json)

## Low-power associated sleep

Shikoku's `wlan.lpas-allowed` and `wlan.aoac-allowed` are both present as zero-length Data in the live PCIe service and its installed board profile. The config manager checks their presence and sets the corresponding permissions. It also has a boot-time override path. Both keys occur in 35 of the 56 board profiles in each stock directory. Two related settings, `wlan.mimo_ps.enabled` and `wlan.ocl.enabled`, appear as zero-length Data in all 56 and on the live service. Radio chain use remains unmeasured. [Stock profile and registry comparisons](../evidence/2026-11-17-radio-power-scheduling.json)

Associated-sleep entry and exit can also request a change to the beacon-based receive width when the relevant feature and board settings are available. [Radio-chain and channel-width policy](radio-chain-policy.md#power-saving-and-width-controls)

In both slices, `checkForLPASSupport` requires the host permission and firmware feature bit 26, which corresponds to `lpas` in the legacy capability table. The reported word and provisioned property agree with those inputs. When the associated-sleep state selects LPAS, the entry path requests mode 1 and the exit path requests mode 0 through the firmware's `lpas` setting. The first five minutes of retained boot logs yielded no matching provisioning or mode messages. The active LPAS state, acknowledgment, radio duty cycle, and wake outcome remain unmeasured. [Mode and gate trace](../evidence/2026-11-17-radio-power-scheduling.json), [Host sleep policy](host-power-policy.md)

## Beacon and DTIM policy

An AP advertises its beacon interval and its DTIM period, the number of beacons between Delivery Traffic Indication Messages. In the signed driver, the internal `getDTIM_INT` handler reads the current period from the BSS manager. The public CoreWLAN getter did not return a usable BSSID in this session, so the current AP could not be matched to its cached beacon information. The recorded test used the association getter alone. [Infineon's DTIM description](https://documentation.infineon.com/psocedge/docs/udx1761932651136), [Apple cached network getter](https://developer.apple.com/documentation/corewlan/cwinterface/cachedscanresults%28%29), [Host observation](../evidence/2026-11-17-radio-power-scheduling.json)

`AppleBCMWLANPowerStateAdapter::configureBeaconSOI` takes a DTIM period, beacon interval, and requested wake period. If the requested interval is at most one beacon interval, it asks for `bcn_li_bcn=1` and `bcn_li_dtim=0`. For a longer request it sets `bcn_li_bcn=0` and computes the extended DTIM count. With positive inputs in the driver's 32-bit arithmetic range and both times in milliseconds, the loop implements

```text
dtim_interval = beacon_interval * dtim_period
dtim_count = max(1, ceil(requested_wake_period / dtim_interval) - 1)
```

For a 100 ms beacon interval and DTIM period of 3, a wake request of 900 ms produces count 2. A request of 901 ms produces count 3. These are the host's requested parameters. Beacon reception and the firmware's effective cadence still require measurement. [Driver math and variables](../evidence/2026-11-17-radio-power-scheduling.json)

Both slices also accept a version-1, 32-byte missed-DTIM event record containing seven values for peer-to-peer, firmware commands, scans, roaming, home channel, sleep, and miscellaneous reasons. The firmware publishes `dtim_miss`, and the literal is present in all three installed images. The event fields could help distinguish sleep from other causes in a captured bench trace. No event values were sampled. [Event parser and firmware search](../evidence/2026-11-17-radio-power-scheduling.json)

## Other firmware power paths

The shared driver also has early-beacon-termination configuration and status paths using `bcntrim` and `bcntrim_status`. Opportunistic power save has `ops_cfg` and `ops_status` paths. Digital Nap uses `nap_enable`. The three related board keys are absent from all 56 installed profiles and the live bus. The live legacy reply omits `bcntrim`, `ops` and `nap`. The presence of these routines establishes what the shared host driver can attempt on eligible hardware. The Shikoku snapshot contains no effective values for these modes. [Driver, profile, and capability evidence](../evidence/2026-11-17-radio-power-scheduling.json)

## Target Wake Time

Target Wake Time schedules Wi-Fi service periods. Both macOS driver slices include two TWT diagnostic argument labels. The scoped searches found zero `twt` or `he_twt` literals in the three stock BCM4378 images, and neither word appears in the running legacy capability reply. An 802.11ax association establishes the PHY mode. TWT eligibility for this station and any accepted agreement remain open. [IEEE 802.11 timing liaison](https://www.ieee802.org/11/Liaisons/2022-12-20-802-11%20liaison%20to%20802-1%20re%20TSN%20support.pdf), [Driver label provenance](driver-timing-provenance.md), [Local evidence](../evidence/2026-11-17-radio-power-scheduling.json)

The pinned Asahi driver sets requester, responder, broadcast TWT, and flexible scheduling bits directly in its station HE capability template. It also queries firmware HE enablement and prints the default HE capability reply in a debug path. The TWT template bits are assigned independently of that reply. `iw phy` can therefore report TWT flags before any negotiation on air has been observed. [Asahi HE template](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7378-L7410), [Firmware HE query](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L7516-L7531)

## Linux power-save control

The pinned stable Linux and Asahi drivers both store the requested power-save policy, then request `PM_FAST` or `PM_OFF` on an up interface. They always request `PM_OFF` for P2P clients in this path. Each driver then requests a separate `pm2_sleep_ret` inactivity timeout capped at 2,000 ms. The first command can log an error while the callback returns the result of the timeout request. The netlink setter passes the kernel's existing timeout and skips the callback if its Boolean already matches. The getter reports that stored Boolean. [Stable driver](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L3304-L3353), [Asahi driver](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L3165-L3214), [Timeout constant](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L86-L93), [Netlink setter and getter](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/net/wireless/nl80211.c#L14969-L15032)

## Bench measurements for periodic workloads

Use a separately managed A2337 and an owned AP. Keep channel, width, and signal conditions fixed. For a device that uploads periodically, compare idle energy and the delivery latency of a small periodic workload across two AP DTIM periods. Record the AP's beacon interval, the station power-save readback, sequence gaps and RTT percentiles. For an associated-sleep trial, record whether the link survives and how long delivery takes after wake. Use a radio-specific counter or measurement for duty cycle and a system power meter for total energy. IOReport value sampling can make firmware requests and belongs on the separate device. [IOReport update path](cca-provenance.md), [Linux bench controls](asahi-controls.md#bench-acceptance-criteria)

On a TWT-capable AP, establish that the responder is active. Record the station's association capability bits and obtain an accepted TWT agreement from AP diagnostics or a passive capture of the test network. Retain the negotiated interval, service period duration, and traffic timing. Compare energy and latency with an identical run before the agreement. A published study on phones observed limited savings and stability costs under its test conditions. [hostapd responder option](https://android.googlesource.com/platform/external/wpa_supplicant_8/+/refs/heads/main/hostapd/hostapd.conf#875), [ICC 2023 measurement study](https://ieeexplore.ieee.org/document/10279666/)

## Reproduce the published properties

Run both commands from the repository root. Compare `wifi.radio_power_config_properties` with the corresponding keys in `platform_config.selected_keys`. The reports distinguish present empty Data from an absent property.

```sh
python3 tools/read_macos_inventory.py
python3 tools/inspect_firmware.py \
  /usr/share/firmware/wifi/C-4378__s-B1/shikoku.trx \
  --platform-config /usr/share/firmware/wifi/shikoku-PlatformConfig.plist
```
