# Wi-Fi and Bluetooth coexistence on the BCM4378

The running Shikoku driver publishes a four-record coexistence table on its PCIe service. The table matches all 56 installed macOS board profiles in both stock directories. The requested BCM4378 NVRAM supplies separate settings that vary across board families. The observations below come from macOS 27.2.1 build 26B131 on the M1 Air, installed files, and static inspection of both signed DriverKit slices. The Wi-Fi link remained active on `en0`. [Evidence and artifact identities](../evidence/2026-11-17-bluetooth-coexistence-policy.json)

## Startup parameters and antenna settings

The I/O Registry property `AppleBCMWLANBusInterfacePCIe.bcom.btc.params` contains 32 bytes. In both driver slices, `AppleBCMWLANCore::setupFirmware` calls `setupFirmwareWithDTDefaults`, which calls `AppleBCMWLANConfigManager::setBTCParameters`. The helper reads successive 8-byte records as little-endian 32-bit IDs and values. It sends one `btc_params` setting per complete record and ignores trailing bytes. If a request fails, the helper can log the failure and continue. Individual firmware acknowledgments and effective parameter values remain unmeasured. [Table and call chain](../evidence/2026-11-17-bluetooth-coexistence-policy.json#L20)

| Parameter ID | Published value |
| ---: | ---: |
| 6 | 15 |
| 8 | 45,000 |
| 9 | 15,000 |
| 10 | 20,000 |

Infineon support describes ID 8 as a Bluetooth deferral limit, ID 9 as a Wi-Fi power-save interval when Bluetooth is the peripheral, and ID 10 as part of the access timing in a CYW43353 discussion. The IDs' semantics and units remain unverified for the BCM4378. [Infineon CYW43353 support discussion](https://community.infineon.com/t5/AIROC-Wi-Fi-and-Wi-Fi-Bluetooth/Bluetooth-audio-streaming-WiFi-inteference/td-p/379269)

All 250 installed BCM4378 NVRAM paths, representing ten distinct payloads, specify `btc_mode=1` and `btc_prisel_ant_mask=0`. The requested `P-shikoku-X3_M-RASP_V-m__m-6.11.txt` specifies `btc_ant_share=0x2`. The table groups file paths by board and includes the default aliases. Firmware interpretation of the antenna values and physical arbitration remain open. [NVRAM groups and selected profile](../evidence/2026-11-17-bluetooth-coexistence-policy.json)

| Boards | Installed profile paths | Antenna setting |
| --- | ---: | --- |
| Shikoku B1, Honshu B1, Kyushu B1 and B3 | 110 | `btc_ant_share=0x2` |
| Capri B1 and Santorini B1 | 90 | `btc_ant_share=0x11` |
| AtlantisB B1 | 50 | `btc_alt_ant_config=0x2` |

Infineon describes mode 1 as full time-division sharing in its CYW43353 discussion. Its general article also shows how board flags can affect the initial mode on supported combo chips. The Shikoku NVRAM establishes the provisioned value. The active BCM4378 mode remains unmeasured. [Infineon mode discussion](https://community.infineon.com/t5/AIROC-Wi-Fi-and-Wi-Fi-Bluetooth/Bluetooth-audio-streaming-WiFi-inteference/td-p/379269), [Infineon default-mode article](https://community.infineon.com/t5/Knowledge-Base-Articles/Using-btc-mode-for-BT-coexistence/ta-p/680099)

## Association protection and internal profile controls

The running `FWCap` string includes `btc_wifi_prot` and `ucm`. The driver's legacy capability table assigns `btc_wifi_prot` to feature bit 15. During a normal association attempt, `AppleBCMWLANJoinAdapter::performJoin` tests this bit before requesting coexistence protection for the four-way handshake. `set4WayHandshakeProtection` queries the firmware variable and handles reply versions 1 and 2 before sending the corresponding configuration. It remains open which version Shikoku returns and how much airtime the association receives. [Live firmware capability provenance](firmware-capabilities.md), [Join trace](../evidence/2026-11-17-bluetooth-coexistence-policy.json)

Shared macOS driver methods handle coexistence profile reply versions 1–3, active-profile selection, 2.4 GHz shared-chain control and an AP stream-count limit. They reference `btc_profile`, `btc_profile_active`, `btc_2g_shchain_disable` and `btc_nss`. All three distinct installed `.trx` payloads contain the literal substrings `btc_params`, `btc_mode` and `btc_wifi_prot`. The searches found zero occurrences of `btc_profile`, `btc_2g_shchain_disable` and `btc_nss` in those payloads. These observations leave the live profile, firmware command support and application access open. [Driver and payload evidence](../evidence/2026-11-17-bluetooth-coexistence-policy.json)

## Antenna time and contention telemetry

The live public IOReport legend lists 56 channels under `BT Coex`. The labels cover antenna requests and grants, WLAN preemptions, reservation states, Bluetooth request reasons including eSCO, A2DP and BLE, and extra audio and protection counters. Both DriverKit slices contain eight versioned event parsers that pass normalized data to `IO80211Controller::setBTCoexstat`. In the installed IO80211DriverKit cache the controller forwards the report to its monitor and feeds a separate WLAN lost-antenna calculation to the infrastructure interface. The set of labels describes the available reporting schema. Values and the event version used by the running firmware were outside this snapshot. [All labels and consumer evidence](../evidence/2026-11-17-bluetooth-coexistence-policy.json)

Both version-12 parsers also decode a 5 GHz coexistence record with deferral counts and maximum switching durations. The legacy driver table assigns `bt5gcx` to feature bit 120. The Shikoku capability reply did not contain that word. Whether this firmware populates the 5 GHz record remains open. [Firmware capability snapshot](../evidence/2026-11-17-live-firmware-capabilities.json), [5 GHz parser evidence](../evidence/2026-11-17-bluetooth-coexistence-policy.json)

The monitor writes three values to `Coex Snapshot` when the elapsed window reaches at least 4,501 ms. The channel IDs in the installed code match those in the live legend. This path accumulates event-reported Bluetooth duration in whole milliseconds before calculating usage. [Snapshot IDs and calculation](../evidence/2026-11-17-bluetooth-coexistence-policy.json)

| Label | Value written by the host monitor |
| --- | --- |
| `BTDuration(s)` | Difference between the whole-second endpoints of the host measurement window |
| `BTUse(%)` | Integer percentage from accumulated event-reported Bluetooth duration divided by elapsed window time |
| `TS(ms)` | Host calendar time in milliseconds |

Reading the published legend uses I/O Registry properties. IOReport value sampling can send firmware diagnostic requests in the same driver stack. Counter validation belongs on a separately managed test machine that can tolerate a Wi-Fi interruption. [IOReport sampling trace](cca-provenance.md)

## Linux and Asahi comparison

The pinned stable Linux and Asahi versions have byte-identical `brcmfmac/btcoex.c` files. Their cfg80211 critical-protocol hook accepts DHCP, suppresses scanning and aborts a scan in progress. The driver's coexistence state machine starts parameter changes only after three matching SCO or eSCO indicators in up to twelve samples. It initially tries to save and change three values. If DHCP remains pending after the opportunity window, nominally two seconds, it can try a further five changes. On completion it attempts to restore the saved values. The measured behavior of the BCM4378 under this policy remains open. [Linux DHCP hook](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L5797-L5828), [Linux state machine](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/btcoex.c), [Pinned Asahi source](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/btcoex.c)

## Measure a concurrent workload

Use a separately managed A2337, an owned access point and a Bluetooth headset or BLE sensor. Run the same local Wi-Fi workload on fixed 2.4 GHz and 5 GHz channels at the same width. For each band, collect an idle-Bluetooth baseline and repeat with a steady audio stream or sequence-numbered BLE notifications. Record the Wi-Fi throughput and RTT distribution along with the Bluetooth gap or loss distribution. The several-second snapshot can align with sustained phases. Application timestamps resolve individual gaps. Time association and DHCP separately on the bench to see how much of any disruption occurs during setup. The A2337 lab test establishes simultaneous emissions under test conditions. Scheduling behavior for these workloads remains to be measured. [A2337 simultaneous RF measurements](a2337-rf-tests.md), [BLE notification experiment](bluetooth-firmware.md#coexistence-experiment)

## Reproduce the parameter decode

Run these from the repository root. Compare `platform_config.selected_keys["bcom.btc.params"]` with `wifi.coexistence_parameters`. The second command reads the published bus property.

```sh
python3 tools/inspect_firmware.py \
  /usr/share/firmware/wifi/C-4378__s-B1/shikoku.trx \
  --platform-config /usr/share/firmware/wifi/shikoku-PlatformConfig.plist
python3 tools/read_macos_inventory.py
```
