# Running BCM4378 firmware capabilities on macOS

The running Shikoku driver publishes the firmware's capability string as `AppleBCMWLANCore.FWCap`. The sample on macOS 27.2.1 build 26B131 contains 90 words and 89 distinct values. It also publishes `wlan.hw.feature-flags = 0`. The PCIe service publishes `WiFiCapability.ranging = true` and `WiFiCapability.awdl = true`. The registry reader queried properties on the active device while `en0` remained the default interface. [Live capability snapshot](../evidence/2026-11-17-live-firmware-capabilities.json), [I/O Registry property getter](https://developer.apple.com/documentation/iokit/1514293-ioregistryentrycreatecfproperty/)

## Where the firmware words come from

In both signed driver slices, the successful `AppleBCMWLANCore::IssueFwCap` path queries the firmware's legacy `cap` variable, terminates the response string, and publishes it as `FWCap`. The code then matches complete words against a compiled table and sets or clears the corresponding feature bits. The two slices have the same 86 table entries. Forty-eight entries match the published words exactly. The driver also tests some words separately, including `csi`. The snapshot records the last published legacy answer. It leaves the current state of individual features and the contents of the separate extended capability reply open. [Driver table and live words](../evidence/2026-11-17-live-firmware-capabilities.json)

| Capability words in the live report | What the observation establishes |
| --- | --- |
| `proxd`, `nan`, `nanrange`, `awdl` | Firmware advertises proximity ranging and both peer Wi-Fi families. App access and ranging exchanges have separate evidence below. |
| `rsdb` | The running firmware advertised simultaneous dual-band capability. Live cached slice capabilities, transmit policy and concurrent airtime remain open. [Dual-band policy trace](simultaneous-dual-band.md) |
| `btc_wifi_prot`, `ucm` | The join code checks the feature bit associated with `btc_wifi_prot` before asking for four-way handshake protection. The applied coexistence profile remains unmeasured. [Coexistence policy trace](bluetooth-coexistence-policy.md) |
| `lpas`, `dtim_miss` | Firmware advertises low-power associated sleep and missing-DTIM diagnostics. The driver's LPAS gate also checks board permission. [Radio power policy and diagnostics](radio-power-scheduling.md) |
| `dfsp` | The legacy driver checks this word and the board's DFS proxy permission. Both inputs are present on Shikoku. The live session mode remains unmeasured. [DFS proxy and channel policy](dfs-proxy-policy.md) |
| `single-user-beamformer`, `single-user-beamformee`, `multi-user-beamformee` | The firmware reports all three beamforming roles. The session used for the snapshot did not measure sounding or beamforming over the air. [A2337 radio tests](a2337-rf-tests.md) |
| `arpoe`, `ndoe`, `tko`, `pktfltr2` | The firmware advertises ARP, neighbor discovery, TCP keepalive and packet filter features. The current offload state and behavior during sleep remain unmeasured. [Host power policy](host-power-policy.md), [Linux ARP and ND offloads](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/core.c), [Infineon TKO terminology](https://community.infineon.com/t5/Wi-Fi-Combo/Infineon-AIROC-Wi-Fi-BT-Combo-STM32-Expansion-Pack-1-4-0-Official-Release-Build/td-p/435548) |
| `ecounters`, `adv_ecounters`, `phy_ecounter`, `phy_cal_ecounter` | The firmware advertises event and PHY telemetry families. The macOS sampling path can issue commands to firmware, so the registry sample only reads the published words. [IOReport provenance](cca-provenance.md) |

## Ranging on the BCM4378

The `AppleBCMWLANChipManagerPCIe4378` initializer sets ranging support. At PCIe attach, the driver applies a separate host hardware-policy disable flag and then publishes the surviving Boolean in `WiFiCapability`. Both signed slices implement this sequence. The live Boolean confirms that the running driver's chip-level gate passed for Shikoku. [Chip initializer and registry evidence](../evidence/2026-11-17-live-firmware-capabilities.json)

The legacy table maps the live firmware word `proxd` to driver feature bit 48. The extended capability parser has a separate branch that can set the same bit. `checkForRangingEnabled` requires bit 48 and a clear ranging-disable bit in the core's hardware-policy field. `getCARD_CAPABILITIES` uses the same condition when building its reply. The published firmware word and zero hardware-policy value satisfy the inputs to that condition on the legacy path. The live registry contains no measured distance or session result. [Capability and policy trace](../evidence/2026-11-17-live-firmware-capabilities.json)

`AppleBCMWLANInfraProtocol::getRANGING_CAPS` returns `kIOReturnUnsupported` directly in both slices. Shared core methods have separate paths for enabling and starting FTM-related ranging and handle firmware ranging events. The two PROXD status logs label a field `core supported`. The event parser obtains it from the low byte of a 16-bit status field and uses the high byte as the core ID. That field is per-event, while the chip eligibility and firmware capability words come from initialization. Its on-device value remains unmeasured. [Earlier diagnostic investigation](driver-timing-provenance.md), [Event trace](../evidence/2026-11-17-live-firmware-capabilities.json)

The signed driver includes a `wlan.ranging.params` profile lookup and a firmware ranging-configuration path. None of the 56 installed macOS board profiles supplies that exact key. The BCM4378 NVRAM proximity offsets are present in the earlier artifact sample. Applying those offsets, obtaining actual ranging results, and determining which peer protocols interoperate remain separate bench measurements. Apple documents peer-to-peer Wi-Fi distance estimation for Auto Unlock between paired devices. A test of that supported feature on an owned bench can establish whether the intended Apple workflow completes. Measuring interoperability with a standards-based FTM responder requires its own exchange. [Timing and calibration evidence](../evidence/2026-11-17-wifi-timing-capabilities.json), [Apple Auto Unlock design](https://support.apple.com/en-za/guide/security/sec6ab47ebfc/web)

The firmware also advertises `nanrange`, and macOS registers a `nan0` interface. The installed native macOS 27.2 SDK marks `WACapabilities` unavailable. A small program using its supported-feature getter failed native compilation. The Apple SDK and the live firmware capability string establish different layers of support. [Driver interfaces](driver-interfaces.md), [Compile result](../evidence/2026-11-17-live-firmware-capabilities.json), [Apple Wi-Fi Aware device list](https://developer.apple.com/documentation/wifiaware), [Apple Developer Technical Support](https://developer.apple.com/forums/thread/827887)

## CSI sensing in the shared driver

Both slices contain `AppleBCMWLANSensingAdapter`. Its data path requires the driver's sensing-capable bit and an OS feature flag. The legacy detector sets the sensing-capable bit only when the response contains `csi`, and clears it otherwise. The published response contains no `csi` word. On that legacy input the sensing adapter's firmware gate is clear. The signed driver's presence and the live proximity-ranging flags leave per-subcarrier CSI, FFT samples, and IEEE 802.11bf operation unverified on this BCM4378. [Driver and firmware evidence](../evidence/2026-11-17-live-firmware-capabilities.json), [IEEE 802.11bf specification](https://standards.ieee.org/ieee/802.11bf/11574/), [Sensing evidence and bench options](spectrum-sensing.md)

## Reproduce the registry snapshot

```sh
python3 tools/read_macos_inventory.py
```

The relevant fields are under `wifi.capability_inputs`. An unavailable or malformed firmware property yields `null` for `firmware_capability_words`. The reader uses only the published registry state and installed property lists for the capability snapshot. The signed driver table can be checked with `llvm-objdump` and `dyld_info -fixups` by following the table access from `IssueFwCap` in each slice. [Inventory reader](../tools/read_macos_inventory.py)
