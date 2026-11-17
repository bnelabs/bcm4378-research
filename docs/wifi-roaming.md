# Wi-Fi roaming policy on the BCM4378

Apple documents a −75 dBm roam trigger and a candidate 12 dB stronger than the current BSS for Apple silicon Macs. It also documents 802.11k neighbor reports, 802.11v BSS Transition Management and 802.11r Fast BSS Transition. Neighbor reports help a client find candidates, BSS Transition Management lets the network recommend them, and Fast BSS Transition speeds up authentication during a move to another BSS. [Apple deployment guide](https://support.apple.com/en-gu/guide/deployment/dep98f116c0f/web), [Apple assisted roaming support](https://support.apple.com/en-us/103274)

## Shikoku board settings and driver paths

On macOS 27.2.1 build 26B131, the running `AppleBCMWLANBusInterfacePCIe` exports eight roaming-related properties that match the installed Shikoku PlatformConfig byte for byte. The 56 installed macOS board profiles share one payload per key for `bcom.roam.default`, `bcom.roam.enterprise` and the 528-byte `bcom.roam.profiles` table. [Platform and registry readback](../evidence/2026-11-17-roaming.json)

| Shikoku legacy profile | 2.4 GHz trigger | 2.4 GHz quality delta | 5 GHz trigger | 5 GHz quality delta |
| --- | ---: | ---: | ---: | ---: |
| Default | −75 dBm | 20 dB | −75 dBm | 10 dB |
| Enterprise | −70 dBm | 12 dB | −70 dBm | 12 dB |

Both signed driver slices load 20 bytes for each short profile in `gatherParameterData`. The enterprise profile falls back to the default bytes when its property read fails. The enterprise trigger getter reads the signed halfword at byte 12. In the enhanced-roaming branch, the driver uses the words at bytes 16 and 18 to configure the firmware. The driver's diagnostics name adjacent trigger and quality-delta pairs for 2.4 and 5 GHz. The inventory now decodes those pairs and retains the leading six words for comparison. The selected runtime profile and the conditions that make this Mac roam remain to be measured. [Signed driver trace and decoded values](../evidence/2026-11-17-roaming.json)

The legacy roaming setter in both signed driver slices loops over up to three slots at a 22-byte stride. Interpreting the 528-byte table at that stride gives eight groups of three slots and 12 populated slots. The populated slots precede the zero-filled slots in every group. This supports the grouping as a candidate layout. The table consumer and the conditions that select each group remain open. [Slot layout and driver evidence](../evidence/2026-11-17-roaming.json)

The legacy firmware response includes `wnm`, `fbtoverds` and `fbt_adpt`. Shikoku supplies `wlan.wnm.enabled` as the four bytes `01 00 00 00`. The driver's KVR initialization combines the platform property with the caller's enable flag. Separate driver paths configure FT over the distribution system and the BSS Transition Management RSSI threshold. The latter gets its input from a WNM configuration record. Its applied value remains open. [Legacy firmware capabilities](firmware-capabilities.md), [Driver paths and property bytes](../evidence/2026-11-17-roaming.json)

The pinned stable Linux and Asahi brcmfmac paths initialize a −75 dBm trigger and 20 dB delta across bands. They also select different beacon-timeout values depending on whether built-in roaming is enabled. These are driver defaults in the pinned source. The roam decisions and timeout on an A2337 running Asahi remain unmeasured. [Stable initialization](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L6914-L6962), [Asahi initialization](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L6878-L6926), [Pinned defaults](../evidence/2026-11-17-roaming.json)

## Published readouts and a bench measurement

Run the inventory for the published keys and legend under `wifi.roaming`. The legend includes BSSID changes, roam success and failure, roam preparation and scan start and end for `en0`, plus scan count and off-channel duration labels for both slices. The inventory reads catalog metadata. The CoreWLAN sampler gives time-stamped RSSI and channel. CoreWLAN also has a BSSID-change callback, with an app entitlement listed in Apple's event-monitoring documentation. [Inventory tool](../tools/read_macos_inventory.py), [CoreWLAN event methods](https://developer.apple.com/documentation/corewlan/cweventdelegate), [Event monitoring entitlement](https://developer.apple.com/documentation/corewlan/cwwificlient/startmonitoringevent%28with%3A%29)

```sh
python3 tools/read_macos_inventory.py
swift tools/read_wifi_status.swift --sample 25 0.5
```

For a roam test, use a separate A2337 and two owned access points. Keep their SSID and security mode consistent. Hold the client and attenuation trajectory constant across runs, adjust 802.11k, 802.11v and 802.11r preferences through the AP's documented configuration, and record both AP timestamps and the client RSSI. Capture both channels using independent receivers if needed. Measure BSS changes and the gap in successful probes to an owned LAN endpoint. The loss interval and the management-frame timing can differ because the client may continue sending data during part of the transition.

Use the following on a saved capture to identify FT authentication over the air, FT action frames over the distribution system, and reassociation with an FT element. A candidate exchange is confirmed by matching the test-client and AP endpoints and checking reassociation status. The evidence records additional filters for neighbor reports and BSS Transition Management. Protected management frames may require AP-side diagnostics to observe the equivalent exchange. [Wireshark WLAN fields](https://www.wireshark.org/docs/dfref/w/wlan.html), [NXP 802.11kvr lab application note](https://www.nxp.com/docs/en/application-note/AN14212.pdf)

```sh
tshark -n -o wlan.enable_decryption:FALSE -r /path/to/bench-capture.pcapng \
  -Y 'wlan.fixed.auth.alg == 2 || wlan.fixed.category_code == 6 || (wlan.fc.type_subtype in {2, 3} && wlan.tag.number == 55)' \
  -T fields -e frame.number -e wlan.fc.type_subtype -e wlan.fixed.auth_seq -e wlan.fixed.status_code
```

Wireshark's public FT-PSK and FT-SAE fixtures each show two FT authentication frames and the reassociation request and successful response. The FT-EAP fixture advertises a mobility domain and returns zero frames from the FT exchange filter. This demonstrates a way to tell whether the AP advertised fast transition or a client actually exercised it. The A2337's own 802.11k, 802.11v and 802.11r exchanges remain to be captured. [Wireshark fixtures](https://github.com/wireshark/wireshark/tree/v4.6.9/test/captures), [Filter results and hashes](../evidence/2026-11-17-roaming.json)
