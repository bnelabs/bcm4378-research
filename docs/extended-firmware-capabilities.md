# Extended firmware capability parsing

The BCM4378 on this Mac publishes `hp2p`, `ap`, and `awdl` in its legacy firmware capability reply. Apple's signed driver also has a versioned parser with a wider feature vocabulary. Its direct writes cover 85 distinct driver feature bits. The stock registry snapshot and the parser map come from macOS 27.2.1 build 26B131, with running firmware `18.20.511.0.7.8.207` and FWID `01-2606388a`. [Live snapshot and signed driver trace](../evidence/2026-11-17-extended-firmware-capabilities.json)

## Which parser supplies `FWCap`

`AppleBCMWLANCore::processChipCaps` clears a 16-byte feature bitmap and calls `adjustFeatureFlags` to apply host defaults and policy. It normally tries `IssueFwCapExt` first. That routine reads `dngl:capext`, checks the bounds of the returned data, walks tagged records, and calls `processFwFeatures`. A zero return from `IssueFwCapExt` skips legacy discovery. An extended-path error or an internal boot policy can route discovery to `IssueFwCap`, which publishes the text returned for `cap` as `FWCap`. Both installed driver slices implement this sequence. [Dispatch and publisher addresses](../evidence/2026-11-17-extended-firmware-capabilities.json)

The registry read repeated the same 90 words in the same order while `en0` was active. The published property confirms that the legacy query succeeded at least once on this driver service. The property carries no timestamp or selection reason. A 24-hour query of retained dispatch messages timed out, leaving the most recent parser and the reason for selecting the legacy path unresolved. [Registry and retained-log evidence](../evidence/2026-11-17-extended-firmware-capabilities.json)

## What the extended parser can set

In each slice, `processFwFeatures` has 77 direct Set calls covering 84 distinct indices and 21 direct Clear calls covering 19 distinct indices. One shared Set call receives eight possible values through different branches. Eighteen indices appear in both sets, so the result can depend on firmware fields and subsequent policy checks. The numbers describe reachable literal arguments to the driver's feature-bit methods. They leave the current bitmap and the full firmware record layout unresolved. [Per-slice counts, sets, and shared callsite](../evidence/2026-11-17-extended-firmware-capabilities.json)

The legacy table names 86 indices. The extended parser can directly set 77 of those, including proximity ranging (`proxd`, 48) and timing support (`tsync`, 52 and `ptm`, 91). It can clear `nanho` at bit 64 and has no direct Set call for that bit. The separate legacy `csi` check uses bit 97, which is absent from both direct call sets of the extended parser. The current `FWCap` has no `csi` word, so the sampled legacy input leaves the sensing gate clear. [Legacy capability trace](firmware-capabilities.md), [Timing paths](packet-timestamps.md)

Seven indices the extended parser can set sit outside the compiled legacy word table. The legacy routine handles 11 and 86 separately.

| Driver bit | Verified consumer in both installed slices |
| --- | --- |
| 11 | Blocks `shouldSupportTethering` before that method tests AP bit 16. The separate legacy `ap` check clears bit 11 when `ap` is present. |
| 86 | Returned by `checkForHP2PSupport`. A separate legacy `hp2p` check sets this bit when the word is present. |
| 105 | Tested by `checkForBeaconProtectionSupport`. |
| 106 | Tested with bit 105 before the setup path calls `setBeaconProtectionParams`. Its individual meaning remains unresolved. |
| 115 | Tested by `cmdMloStatus` and before the driver initializes its 802.11be adapter. |
| 116 | Tested after the beacon's EHT check in `getBssPhyModde`. |
| 121 | Controls a flag in the card-capability reply. Its feature name remains unresolved. |

The MLO and EHT consumers establish code paths in Apple's shared driver. Apple specifies 802.11ax Wi-Fi 6 for the M1 MacBook Air, and this snapshot gives no evidence of Wi-Fi 7 operation on the BCM4378. [Consumer addresses](../evidence/2026-11-17-extended-firmware-capabilities.json), [Apple model specifications](https://support.apple.com/en-us/111883)

## HP2P on the BCM4378

On the observed legacy input, the signed driver sets bit 86 and follows up with a firmware control read. The extended parser also calls the same read helper after setting bit 86. The NAN interface has a separate `getHP2P_CAPS` entry that reaches a firmware query scoped to that interface. Two bits in the follow-up core reply govern RLLW and split transmit status. The live values of those bits and their relationship to any specific AirDrop or Wi-Fi Aware exchange remain unmeasured. [Core and NAN interface callsites](../evidence/2026-11-17-extended-firmware-capabilities.json), [HP2P reply and firmware records](hp2p-low-latency.md)

The published words contain `hp2p` and omit the standalone `p2p` word. Applying the pinned stable brcmfmac substring matcher to that saved list classifies it as `BRCMF_FEAT_P2P` because it finds `p2p` inside `hp2p`. Applying the pinned Asahi whole-word matcher leaves that feature clear on the same input. This offline comparison gives a concrete check for future cross-platform tests. It uses the macOS reply, while the Linux firmware's own reply and peer behavior require a separate sample. The same substring problem was reported upstream on other Broadcom parts. [Offline comparison](../evidence/2026-11-17-extended-firmware-capabilities.json), [Pinned stable source](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/feature.c#L228-L250), [Pinned Asahi source](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/feature.c#L244-L274), [Broadcom maintainer discussion](https://lore-kernel.gnuweeb.org/brcm80211/20261108192000.2a1d416e%40kait2en-mbp15-1/T/)

## Reproduce the offline map

```sh
python3 tools/audit_fw_feature_calls.py \
  /System/Library/DriverExtensions/com.apple.DriverKit-AppleBCMWLAN.dext/com.apple.DriverKit-AppleBCMWLAN
```

The auditor uses the local Xcode command-line tools to disassemble the supplied two-slice AppleBCMWLAN executable. It follows immediate arguments and incoming branches to direct Set and Clear calls, and stops with an error if a call argument uses an unfamiliar instruction pattern. The command reads the executable from disk. [Offline auditor](../tools/audit_fw_feature_calls.py)
