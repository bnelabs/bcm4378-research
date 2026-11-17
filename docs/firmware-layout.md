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

The B1 pair has 678,203 equal bytes out of 1,496,769 at the same offsets. Searching for unique exact 4 KiB anchors independently of alignment and extending the strongest matches revealed a **201,010-byte** common region in B1 and a **195,250-byte** region in all three. The three-way span starts at file offsets 1,295,710, 1,294,998 and 1,027,534 respectively. Its byte pattern distinguishes it from the common zero run. Its internal role remains unresolved. [Offline comparison method and results](../evidence/2026-11-17-firmware-comparison.json)

Both B1 images contain the selected literal `wnm_btm_rssi_thresh`. The B3 image contains other WNM labels and has zero exact hits for this one. This corrects the earlier count of ten shared positive markers. Runtime roaming policy remains unmeasured. [Literal counts](../evidence/2026-11-17-firmware-comparison.json)

REA retained whole-file measurements for Honshu (`ev_186a126d3c11596de007eda0924b9618b278e7b5963f1e1c2a5a1f64a7b6062e`), Capri (`ev_65bf19f00ba99813c057b23b1ef5bcdb244074dbb6ddee977e238e0bcbddd7af`) and Kyushu (`ev_ea0e5065f3b137c51198a9183340e123b41f8209e92808a21337ba7b02db1dc6`). The entropy values characterize byte distributions. Code and data boundaries require independent evidence.
