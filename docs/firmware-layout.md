# Firmware layout and board selection

## Files requested by the running driver

`AppleBCMWLANCore.RequestedFiles` returned one set for BCM4378 B1. It names Shikoku X3 and the RASP NVRAM profile with vendor token `m` and revision `6.11`. Each file in the active driver bundle is byte-identical to its counterpart under `/usr/share/firmware/wifi`. The firmware build tag matches the running driver version and firmware ID `01-2606388a`. [Host snapshot](../evidence/2026-11-17-macos-inventory.json), [Firmware tag and digest](../evidence/2026-11-17-firmware.json)

All three distinct executables include the code that announces ThreadX 5.6. [Initialization and thread fault-report disassembly](rtos-threadx.md)

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
| TxCap | 633 bytes | The `TXCP` record contains the profile label `Shikoku_Final_WIFICap_2020Aug25_v1.0` and timestamp text `2026-08-11 16:04:16`, with no encoded timezone. [Profile evidence](../evidence/2026-11-17-txcap-profiles.json) |
| NVRAM | — | The selected 7,690-byte ASCII profile has 296 distinct assignments, including 249 flat keys and 47 `slice/1/` keys. Its `sromrev` field is `11`. [Infineon SROM field description](https://www.infineon.com/assets/row/public/documents/30/42/infineon-an215294-cyw4335-otp-programming-and-nvram-applicationnotes-en.pdf) |

The checks describe the contents at the three paths named by the driver. The applied per-device calibration and transmit-power limits remain unmeasured.

All 35 CLM names resolve to seven validated payloads across both installed firmware roots. The B1 and B3 Kyushu files share their 104-byte CLM header. Three dataset bytes and their corresponding CRC fields account for all differences. [CLM profile audit](clm-profile-audit.md)

The three compiled firmware images also include minimal embedded CLM data. Their general channel descriptors are empty, and the loader also has a path for the downloaded board file. The running interface reports the external Shikoku file's version. [Embedded fallback and active file](clm-channel-tables.md#the-compiled-firmwares-embedded-data)

All 35 installed BCM4378 TxCap names resolve to seven whole-file identities. In each distinct first record, `TXCP` precedes a little-endian word with value 4, a 64-byte zero-padded label field and a 20-byte NUL-terminated timestamp field. This places the remaining body at record offset 92. The meaning of the word at offset 4 remains unknown. [TxCap profile inventory](../evidence/2026-11-17-txcap-profiles.json)

The body hashes form four groups. AtlantisB, Capri and Santorini share one 148-byte body. Honshu and Shikoku each have a distinct 541-byte body, and Kyushu B1 and B3 share a third 541-byte body. The two Kyushu files differ in two timestamp characters and eight CRC bytes. All seven carry the same four-byte second record. The body hashes can track changes independently of packaging timestamps. The field meanings and live RF limits still require separate evidence. [Profile and checksum comparison](../evidence/2026-11-17-txcap-profiles.json)

```sh
bcm_sidecars=/System/Library/DriverExtensions/com.apple.DriverKit-AppleBCMWLAN.dext/Firmware/C-4378__s-B1
python3 tools/inspect_radio_sidecars.py \
  --clm "$bcm_sidecars/shikoku-X3.clmb" \
  --txcap "$bcm_sidecars/shikoku-X3.txcb" \
  --nvram "$bcm_sidecars/P-shikoku-X3_M-RASP_V-m__m-6.11.txt" --nvram-topology
```

### NVRAM chain declarations

All ten distinct stock BCM4378 NVRAM payloads declare `sromrev=11` and set `aa2g`, `aa5g`, `rxchain` and `txchain` to 3, a mask with two bits set. Infineon defines those fields as per-band antenna availability and TX/RX path masks on a related Broadcom family. Apple specifies two spatial streams on both bands for the M1 Air. The stock masks give a reference for checking stream use against station telemetry on the bench. [Profile comparisons](../evidence/2026-11-17-nvram-topology.json), [Infineon NVRAM field definitions](https://community.infineon.com/gfawx74859/attachments/gfawx74859/WifiBTcombo/3828/1/Infineon-AN225021_CYW43012_OTP_Programming_and_NVRAM_Development-ApplicationNotes-v01_00-EN.pdf#page=5), [Apple Wi-Fi specifications](https://support.apple.com/en-au/guide/deployment/-dep268652e6c/web)

The macOS firmware getter exposes hardware and configured masks to the link-reporting path. Both types of transmit mask contribute to the reported `NSS State`. [Radio-chain policy trace](radio-chain-policy.md)

Across the payloads, 247 of 253 flat keys and 46 of 47 `slice/1/` keys occur in every profile. All ten have one 52-value `slice/1/` array. On each B1 board, the vendor `m` file adds one four-value `slice/1/` array compared with vendor `u`. The two stock directory roots have 250 matching names that resolve to the same filesystem objects across the roots. Kyushu B3 uses the B1 Honshu `u` payload. All ten files put the 2.4 GHz band mask and RF switch map under `slice/1/`. [Alias, namespace and array counts](../evidence/2026-11-17-nvram-topology.json), [Factory band map](simultaneous-dual-band.md#factory-band-assignment)

The B1 NVRAM catalog has two sets of TVPM and temperature declarations. They share the stored backoff and duty-cycle thresholds and differ in their 2.4 GHz backoff, duty-cycle, and transmit-chain tables. [TVPM board comparison](tvpm.md)

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

The selected stock NVRAM contains a slice-1 threshold assignment with a space before the equals sign. The pinned Linux parser drops that assignment. The macOS driver preserves the interior space through text normalization. The firmware's lookup of that spelling remains unverified. [Linux replay](ram-diagnostics.md#stock-text-and-linux-boot-serialization), [macOS normalization and firmware calls](macos-nvram-normalization.md)

### Byte reuse across images

The B1 pair has 678,203 equal bytes out of 1,496,769 at the same offsets. Searching for unique exact 4 KiB anchors independently of alignment and extending the strongest matches revealed a **201,010-byte** common region in B1 and a **195,250-byte** region in all three. The three-way span starts at file offsets 1,295,710, 1,294,998 and 1,027,534 respectively. It contains both D11 programs. The remaining bytes in the span need their own interpretation. [Offline comparison method and results](../evidence/2026-11-17-firmware-comparison.json), [D11 loader trace](../evidence/2026-11-17-d11-microcode-loader.json)

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

Within that span, two initial search windows contain 11,190 and 10,927 aligned eight-byte records. Each record has a zero in the eighth byte. The fourth byte is zero only 20 and 21 times respectively. The second window has a four-byte alignment shift relative to the first. Published Broadcom FullMAC work describes a separate D11 core handling real-time 802.11 MAC work with an embedded microcode image. The loader trace below establishes the two exact stored ranges. [Measured record layouts](../evidence/2026-11-17-microcode-components.json), [TU Darmstadt D11 research](https://www.seemoo.tu-darmstadt.de/theses/emulating-broadcoms-d11-core/)

Both windows use up to 53 bits per little-endian eight-byte record. The first and second windows contain 5,941 and 5,742 records that exceed the legacy b43 decoder's 51-bit limit. A full-file scan across 13 distinct stock images found comparable zero-byte lanes only at window phases 0 and 4 modulo 8. The longest qualifying runs in both BCM4364 files used up to 50 bits. The runs in all eight BCM4387 and BCM4388 files reached 53 bits. The zero lane is a family-wide structural clue. The matched bytes and the microcode build tag identify the BCM4378 windows more narrowly. The modern instruction fields remain open. [Width and alignment measurements](../evidence/2026-11-17-d11-window-profile.json), [Legacy b43 decoder](https://github.com/mbuesch/b43-tools/blob/master/disassembler/main.c#L913-L936)

```sh
python3 tools/inspect_firmware.py /usr/share/firmware/wifi/C-4378__s-B1/honshu.trx \
  --embedded-metadata --lane-window 1295724 89520 --lane-window 1385832 87416 \
  --bcm4378-overlays
```

Both B1 images contain the selected literal `wnm_btm_rssi_thresh`. The B3 image contains other WNM labels and has zero exact hits for this one. This corrects the earlier count of ten shared positive markers. Runtime roaming policy remains unmeasured. [Literal counts](../evidence/2026-11-17-firmware-comparison.json)

REA retained whole-file measurements for Honshu (`ev_186a126d3c11596de007eda0924b9618b278e7b5963f1e1c2a5a1f64a7b6062e`), Capri (`ev_65bf19f00ba99813c057b23b1ef5bcdb244074dbb6ddee977e238e0bcbddd7af`) and Kyushu (`ev_ea0e5065f3b137c51198a9183340e123b41f8209e92808a21337ba7b02db1dc6`). The entropy values characterize byte distributions. Code and data boundaries require independent evidence.

### D11 microcode and core selection

Four adjacent ARM literal slots delimit two stored regions of 90,112 bytes (88 KiB) each under the Linux BCM4378 RAM model. Each region is followed by a four-byte size field that contains 90,112. In all three images, ARM code loads one of the two component pointers and its corresponding size. Both paths pass that pair to the same routine as its second and third arguments. [Static pointer, size and argument evidence](../evidence/2026-11-17-d11-static-references.json), [Linux BCM4378 RAM model](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmfmac/chip.c#L738-L747), [Arm calling convention](https://github.com/ARM-software/abi-aa/blob/main/aapcs32/aapcs32.rst#core-registers)

| D11 unit | Component position in the file | Eight-byte records before padding | Zero padding records |
| --- | --- | ---: | ---: |
| 0 | Later component, one record after the earlier search window's start | 10,926 | 338 |
| 1 | Earlier component | 11,190 | 74 |

The selector reads the D11 unit at context offset `+0x48`. In the traced setup path, attach initializes the unit field to 0. A conditional branch checks for a change in a count from 2 to 1 after reading bits 12–13 of the register at offset `0x1a4` in the mapped core. On that branch the firmware sets the context to unit 1, requests the register block for core ID `0x812` and unit 1, stores the returned pointer at context offset `+0x8c` and calls the microcode selector again. It then restores unit 0 and its mapping. In the attach code, the same unit field also controls use of the `slice/1/` prefix when its value is 1. A nearby attach gate accepts a core revision value of 84. Those are static paths in all three images. The live gate values and frequency used by each unit remain unmeasured. [Startup instructions](../evidence/2026-11-17-d11-microcode-loader.json), [Broadcom MAC core ID](https://android.googlesource.com/kernel/common/+/e017507f37d5cb8b541df165a824958bc333bec3/drivers/net/wireless/brcm80211/include/soc.h), [Broadcom core-selection function](https://android.googlesource.com/kernel/msm/+/51dac98e2868508d38bafffe023c1290de57c699/drivers/net/wireless/bcmdhd/siutils.c)

The copy routine saves the source pointer and length in separate unit-indexed arrays. It uses the register block from context `+0x8c`. When the address-setup guard is zero, the routine sets and reads back object-address offset `0x160` with value `0x03000000`. The stock files initialize the guard to zero. Both paths then stream each four-byte word through object-data offset `0x164`. The register pair and setup value match the older Broadcom driver's published microcode-memory selector and auto-increment path. A complete run with either size would issue **22,528 word stores**, including the padded records. Rizin and LLVM independently decoded the matching ARM instructions. [Three-image instruction trace](../evidence/2026-11-17-d11-microcode-loader.json), [Broadcom register definitions](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmsmac/d11.h#L135-L138), [Published microcode writer](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmsmac/main.c#L2098-L2113)

The two component hashes match across Honshu, Capri and Kyushu. This lets a build comparison establish whether a throughput or fault regression coincides with a change to the stored MAC programs. The tool also checks which component a retained D11 program-memory capture matches. The known stock files and copied-payload fixtures passed, including a one-word difference test. The factory profiles configure unit 0 for 5 GHz and unit 1 for 2.4 GHz. Physical D11 memory, executed instructions, and live assignment of network roles to those units need a separate target. [Component inspector](../tools/inspect_d11_microcode.py), [Factory band map](simultaneous-dual-band.md#factory-band-assignment), [Capture comparison](ram-diagnostics.md#compare-a-d11-program-capture)

```sh
python3 -B tools/inspect_d11_microcode.py /usr/share/firmware/wifi/C-4378__s-B1/honshu.trx
rizin -N -q -a arm -b 16 -m 0x352000 \
  -c 'pD 52 @ 0x473c9c; pD 64 @ 0x473758; pD 126 @ 0x48e48c; q' \
  /usr/share/firmware/wifi/C-4378__s-B1/honshu.trx
```

### ARM ROM overlay map

The common span ends inside the table immediately before the firmware tag. In all three images its first word is eight-byte aligned, strictly increases and lies below the Linux reference RAM base. Its second word maps to a sequence of eight-byte slots in the uploaded image. The sequence begins at file offset 57,344 in all three builds, immediately after the 56,941-byte zero run. Published work on earlier Broadcom parts describes a ROM overlay mechanism with eight-byte replacement slots stored in RAM. [Local table profile](../evidence/2026-11-17-rom-overlay-layout.json), [Linux BCM4378 RAM origin](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmfmac/chip.c#L738-L747), [Broadcom ROM overlay research, section 3.3](https://www.maki.tu-darmstadt.de/media/sfb_maki/forschung_8/awards/Nexmon_2017.pdf#page=4)

Every row's slot contains a wide Thumb branch encoding that points into the file region after the slots and before the table when decoded at the first word's address. Using the second word as the instruction address produces six matching rows in each B1 image and two in B3. Rizin independently agreed with the decoded displacements of all 1,948 matching words. A linear disassembly of the entire slot region also found branches at instruction boundaries using the first-word model in 735 rows for each B1 build and 362 for B3. Together these results support a table of ROM addresses paired with RAM overlay slots. Activation and executed addresses on the live controller remain unverified. [Branch comparisons and disassembly evidence](../evidence/2026-11-17-rom-overlay-layout.json)

| Image | Table file offset | Rows | Referenced slot bytes |
| --- | ---: | ---: | ---: |
| B1 Honshu | 1,490,944 | 768 | 6,144 |
| B1 Capri | 1,490,232 | 768 | 6,144 |
| B3 Kyushu | 1,222,768 | 374 | 2,992 |

The two B1 images share 759 exact table rows. B3 shares two with each B1 image. Both D11 program hashes match across all three. The table, overlay slots, and D11 images provide separate identifiers for comparing firmware updates. The chip-specific overlay detector found zero matching tables in the ten other stock images checked. [Pairwise comparisons and controls](../evidence/2026-11-17-rom-overlay-layout.json), [D11 program hashes](../evidence/2026-11-17-d11-microcode-loader.json)
