# Firmware layout and board selection

## Files requested by the running driver

`AppleBCMWLANCore.RequestedFiles` returned one set for BCM4378 B1. It names Shikoku X3 and the RASP NVRAM profile with vendor token `m` and revision `6.11`. Each file in the active driver bundle is byte-identical to its counterpart under `/usr/share/firmware/wifi`. The firmware build tag matches the running driver version and firmware ID `01-2606388a`. [Host snapshot](../evidence/2026-11-17-macos-inventory.json), [Firmware tag and digest](../evidence/2026-11-17-firmware.json)

| Role | Requested name under `C-4378__s-B1/` | Resolved file | Bytes |
| --- | --- | --- | ---: |
| Executable | `shikoku.trx` | `honshu.trx` | 1,497,470 |
| Board NVRAM | `P-shikoku-X3_M-RASP_V-m__m-6.11.txt` | `P-shikoku_M-RASP_V-m__m-6.11.txt` | 7,690 |
| Country Locale Matrix | `shikoku-X3.clmb` | `shikoku.clmb` | 35,973 |
| Transmit-power caps | `shikoku-X3.txcb` | `shikoku.txcb` | 697 |

The board aliases encode chip stepping, board identifier, antenna profile and radio module selector. Linux's published Apple-platform implementation and the Asahi extractor use those selectors. Published CLM documentation describes channel and regulatory power constraints. Linux loads TxCap and per-device calibration as separate inputs. The file request and hash evidence here establishes the selected files. Applied live per-device calibration values remain unmeasured. [Apple board selection patch](https://lists.openwall.net/netdev/2022/01/04/80), [Asahi parser](https://github.com/AsahiLinux/asahi-installer/blob/main/asahi_firmware/wifi.py#L28-L91), [Infineon Wi-Fi glossary](https://www.infineon.com/assets/row/public/documents/30/96/infineon-wi-fi-glossary-software-en.pdf#page=4), [Linux Wi-Fi configuration](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmfmac/common.c), [Apple device-tree calibration support](https://github.com/AsahiLinux/m1n1/blob/main/src/kboot.c#L937-L974)

## Packaging and integrity

The four selected files each resolve to the same filesystem object through the dext and `/usr/share/firmware/wifi` paths. All four hashes match the earlier inventory. `codesign` strict verification passed for both architectures of the installed DriverKit bundle. Its `files` and `files2` resource records were both empty, and the system reported authenticated root enabled. File identities here come from the resolved objects and their digests. [Local evidence](../evidence/2026-11-17-firmware-loader-evidence.json), [Apple code-signing resources](https://developer.apple.com/documentation/technotes/tn3126-inside-code-signing-hashes#Resources), [Apple signed system volume](https://support.apple.com/guide/security/signed-system-volume-security-secd698747c9/web)

The separate `com.apple.driver.BCMWLANFirmware4378.Hashstore` package declares an `IOImageLoader` personality matching the `com.apple.driver.AppleBCMWLANCore` consumer. Its declared executable is absent from the loose bundle. The runtime verification outcome for the selected files remains unmeasured. [Hashstore metadata](../evidence/2026-11-17-firmware-loader-evidence.json)

## Selected radio sidecars

Both the active CLM request and the TxCap request resolve to Broadcom `BLOB` files with a 60-byte header and two records. The header CRC32 and both record CRC32s agree with the OpenWrt container parser's rules for each file. The identical four-byte trailing records account for the end of both files. Their purpose remains unknown. [Observed headers and checksums](../evidence/2026-11-17-radio-sidecars.json), [OpenWrt BLOB parser](https://github.com/openwrt/firmware-utils/blob/master/src/bcmblob.c)

| Role | First record length | Verified file metadata |
| --- | ---: | --- |
| CLM | 35,909 bytes | The `CLM DATA` header identifies API `Oly.Shikoku`, compiler `1.72.1`, import label `ClmImport: 1.74.1` and release label `v5 Final 251211` in the field named manufacturer. [OpenWrt CLM header definition](https://github.com/openwrt/firmware-utils/blob/master/src/bcmclm.c) |
| TxCap | 633 bytes | The record begins with `TXCP`. Its internal fields and their runtime use remain unverified. |
| NVRAM | — | The selected 7,690-byte ASCII profile has 296 distinct assignments, including 249 flat keys and 47 `slice/1/` keys. Its `sromrev` field is `11`. [Infineon SROM field description](https://www.infineon.com/assets/row/public/documents/30/42/infineon-an215294-cyw4335-otp-programming-and-nvram-applicationnotes-en.pdf) |

The checks describe the contents at the three paths named by the driver. The applied per-device calibration and transmit-power limits remain unmeasured.

```sh
bcm_sidecars=/System/Library/DriverExtensions/com.apple.DriverKit-AppleBCMWLAN.dext/Firmware/C-4378__s-B1
python3 tools/inspect_radio_sidecars.py \
  --clm "$bcm_sidecars/shikoku-X3.clmb" \
  --txcap "$bcm_sidecars/shikoku-X3.txcb" \
  --nvram "$bcm_sidecars/P-shikoku-X3_M-RASP_V-m__m-6.11.txt"
```

## Installed package

| Stepping | Executable names / unique payloads | CLM | TxCap | NVRAM |
| --- | ---: | ---: | ---: | ---: |
| B1 | 30 / 2 | 30 / 6 | 30 / 6 | 240 / 10 |
| B3 | 5 / 1 | 5 / 1 | 5 / 1 | 10 / 1 |

The 45 B1 Shikoku NVRAM names collapse to two payloads, one for each vendor token `m` and `u`. The generic and `ID`, `X0`, `X2`, and `X3` Shikoku executable, CLM and TxCap names collapse to the same three resolved files. Five board platform plists are byte-identical. Kyushu's plist contains those same 31 settings plus one additional key. [Complete alias and digest inventory](../evidence/2026-11-17-board-profiles.json)

## Image structure

| Image | Size in bytes | Firmware ID | Whole-file entropy, bits per byte |
| --- | ---: | --- | ---: |
| B1 `honshu.trx` | 1,497,470 | `01-2606388a` | 6.8652 |
| B1 `capri.trx` | 1,496,769 | `01-8acd757c` | 6.8642 |
| B3 `kyushu.trx` | 1,226,142 | `01-f2cc5189` | 6.7645 |

The three builds report version `18.20.511.0.7.8.207`. All three repeat their first 32-byte block and have a 56,941-byte zero run beginning at file offset 403. Rizin's offline Thumb-2 interpretation of the Honshu opening produces two copies of eight wide branch instructions. The likely vector block and adjacent padding are observable on disk. Their runtime role, load address and memory layout remain open. [Firmware comparison evidence](../evidence/2026-11-17-firmware-comparison.json)

### Reference loading model

Asahi transfers the `.trx` bytes unchanged into the files it packages as `.bin`. The Linux BCM4378 PCIe driver treats the firmware as a flat payload, copies it into device RAM and passes the first little-endian word to reset setup. It handles NVRAM separately. These three files contain no literal `HDR0`, ELF or `RAMS` magic. The optional Linux RAM-size field contains eight bytes of `fa` in every image, so the reference driver's size override does not apply. [Asahi exporter](https://github.com/AsahiLinux/asahi-installer/blob/main/asahi_firmware/wifi.py#L74-L87), [Linux loader](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L1490-L1655), [Linux reset setup](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L1774-L1779), [Image checks](../evidence/2026-11-17-firmware-loader-evidence.json)

Rizin decoded all sixteen opening words in each image as Thumb-2 wide branches. The first branch, interpreted at reset origin zero, reaches a location within the uploaded bytes under Linux's BCM4378 base model. All sixteen destinations fit under the same hypothetical vector placement. The public loader establishes reset use only for the first word. Actual placement of the other entries and macOS runtime mapping remain open. [Linux BCM4378 RAM base](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmfmac/chip.c#L738-L747), [Image checks](../evidence/2026-11-17-firmware-loader-evidence.json)

### Byte reuse across images

The B1 pair has 678,203 equal bytes out of 1,496,769 at the same offsets. Searching for unique exact 4 KiB anchors independently of alignment and extending the strongest matches revealed a **201,010-byte** common region in B1 and a **195,250-byte** region in all three. The three-way span starts at file offsets 1,295,710, 1,294,998 and 1,027,534 respectively. Its byte pattern distinguishes it from the common zero run. Its internal role remains unresolved. [Offline comparison method and results](../evidence/2026-11-17-firmware-comparison.json)

An additional 256-byte anchor survey found **810,357 bytes** of exact reuse between the B1 pair. Honshu contains **301,610 bytes** with verified matches in both other files. The mapper indexes anchors gathered from each file, searches for them at every offset, and expands unique matches by byte equality. The results exclude repeats that lack unique anchors and report a lower bound on reuse. Every reported region was independently slice-checked. Semantic roles remain open. [Complete byte region map](../evidence/2026-11-17-firmware-region-map.json)

| Image | Spans with matches in every other image | Bytes outside long uniform runs and detected reuse |
| --- | ---: | ---: |
| Honshu | 301,610 | 686,966 |
| Capri | 301,610 | 686,148 |
| Kyushu | 301,609 | 845,175 |

```sh
python3 tools/map_firmware_regions.py \
  /usr/share/firmware/wifi/C-4378__s-B1/honshu.trx \
  /usr/share/firmware/wifi/C-4378__s-B1/capri.trx \
  /usr/share/firmware/wifi/C-4378__s-B3/kyushu.trx
```

### Microcode build metadata and record structure

The firmware tag is followed by a second tag, `<UCODE-TAG>`, in all three BCM4378 images. It lists `OlympicAXUcode_1447_100`, revision `48542`, major `1447` and minor `100`. The exact 195,250-byte span and all 24 sampled 256-byte anchors occurred in the three BCM4378 files. None of the ten other distinct installed images checked contained the span or a sampled anchor. Those other files were BCM4364, BCM4387 and BCM4388 variants. [Build tags and comparison records](../evidence/2026-11-17-microcode-components.json)

Within that span, two windows contain 11,190 and 10,927 aligned eight-byte records. Each record has a zero in the eighth byte. The fourth byte is zero only 20 and 21 times respectively. The second window has a four-byte alignment shift relative to the first. Published Broadcom FullMAC work describes a separate D11 core handling real-time 802.11 MAC work with an embedded microcode image. The build tag and record patterns make these two windows candidates for D11 microcode. Their exact logical bounds and runtime roles remain open. [Measured record layouts](../evidence/2026-11-17-microcode-components.json), [TU Darmstadt D11 research](https://www.seemoo.tu-darmstadt.de/theses/emulating-broadcoms-d11-core/)

The common span ends inside a separate eight-byte-record table. Each record has two little-endian words. The first increases strictly and the second increments by eight. The table contains 768 rows in each B1 image and 374 in B3. A single newline separates the final record from `<FW-TAG>`. The field meanings remain open. [Table measurements](../evidence/2026-11-17-microcode-components.json)

```sh
python3 tools/inspect_firmware.py /usr/share/firmware/wifi/C-4378__s-B1/honshu.trx \
  --embedded-metadata --lane-window 1295724 89520 --lane-window 1385832 87416
```

Both B1 images contain the selected literal `wnm_btm_rssi_thresh`. The B3 image contains other WNM labels and has zero exact hits for this one. This corrects the earlier count of ten shared positive markers. Runtime roaming policy remains unmeasured. [Literal counts](../evidence/2026-11-17-firmware-comparison.json)

REA retained whole-file measurements for Honshu (`ev_186a126d3c11596de007eda0924b9618b278e7b5963f1e1c2a5a1f64a7b6062e`), Capri (`ev_65bf19f00ba99813c057b23b1ef5bcdb244074dbb6ddee977e238e0bcbddd7af`) and Kyushu (`ev_ea0e5065f3b137c51198a9183340e123b41f8209e92808a21337ba7b02db1dc6`). The entropy values characterize byte distributions. Code and data boundaries require independent evidence.
