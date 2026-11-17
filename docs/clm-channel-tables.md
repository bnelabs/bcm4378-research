# CLM channel tables and the active country plan

The seven distinct BCM4378 regulatory profiles (CLM files) carry the same 38 general 20 MHz channels. The stock interface offered 37 in the sample, with country code `TR` in I/O Registry. The sole difference was channel 144 at 5,720 MHz. The A2337 lab report documents that test center, and the running driver includes it in its clear-channel assessment (CCA) report catalog. [Local comparison](../evidence/2026-11-17-clm-channel-tables.json), [Lab channel comparison](spectrum-sensing.md#match-to-the-stock-channel-list), [CCA report catalog](cca-provenance.md)

If an access point is missing from this Mac, compare its primary channel and width to the stock reported list. Record the country and CLM build when comparing different Macs or OS versions. These fields distinguish a channel-plan difference from weak reception in a case where the access point uses a channel absent from the list. The exact firmware rule responsible for the observed omission remains unresolved.

## General channel ranges in the stock files

The audit checks the existing BLOB and record checksums, then resolves the lookup pointers within the verified `CLM DATA` record. Slots 0 and 1 are OpenWrt's identified 2.4 and 5 GHz range descriptors. Each descriptor contains a little-endian count and record pointer. The two public tables and the three additional nonempty lists use three-byte rows. The third byte behaves as a channel-number step across the stock files. [OpenWrt CLM reader](https://lxr.openwrt.org/source/firmware-utils/src/bcmclm.c#L42), [Audit output](../evidence/2026-11-17-clm-channel-tables.json)

| Lookup slot | Interpretation | Inclusive channel ranges and step | Center frequencies (MHz) |
| ---: | --- | --- | --- |
| 0 | 2.4 GHz primary | 1–13, step 1 | 2,412–2,472 in steps of 5 |
| 1 | 5 GHz primary | 36–64, 100–144 and 149–165, step 4 | 5,180–5,320, 5,500–5,720 and 5,745–5,825 in steps of 20 |
| 25 | Inferred 2.4 GHz 40 MHz centers | 3–11, step 1 | 2,422–2,462 in steps of 5 |
| 26 | Inferred 5 GHz 40 MHz centers | 38–62, 102–142 and 151–175, step 8 | 5,190–5,310, 5,510–5,710 and 5,755–5,875 in steps of 40 |
| 27 | Inferred 5 GHz 80 MHz centers | 42–58, 106–138 and 155–171, step 16 | 5,210–5,290, 5,530–5,690 and 5,775–5,855 in steps of 80 |
| 28 | Another descriptor | Zero count and zero record pointer | — |

The wider-channel interpretations follow from the spacing of the entries. The 5 GHz numbers include the centers in the A2337 lab tests. At each width, the comparison treats a center as matched when CoreWLAN reported every primary in its block. The 5 GHz 40 MHz centers 142, 167 and 175 and 80 MHz centers 138 and 171 had no primaries advertised at the corresponding width. The CoreWLAN snapshot reported 2.4 GHz only at 20 MHz. [A2337 5 GHz exhibit](https://device.report/m/9dbefd8fa57734334f25d9b4c27352a2b1333e4a7384c14f77fb813ec85822d7.pdf#page=5), [Wide-center comparison](../evidence/2026-11-17-clm-channel-tables.json)

## Region codes and profile identity

Slot 10 points to a descriptor with 222 nine-byte rows in every tested file. The first two bytes are a distinct uppercase alphanumeric code per row. All seven files have the same code set, including `TR`, `US`, `JP`, `X2` and `X3`. The rest of the row remains opaque. The full directory has three distinct digests across the files, and the `TR` row matches in all seven. A code row is one part of the rules data. The links from those rows to effective channel permissions and power limits remain open. [Local directory comparison](../evidence/2026-11-17-clm-channel-tables.json), [Infineon CLM manual](https://community.infineon.com/gfawx74859/attachments/gfawx74859/twwifimcu/251/1/Infineon-AN225347_-_Infineon_Wi-Fi_CLM_regulatory_manual-ApplicationNotes-v03_00-EN.pdf)

Slot 24 points to the creation timestamp. The complete version record published by this Mac's driver gives API 21.0, data build `Oly.Shikoku`, compiler `1.72.1`, import `1.74.1`, customization `v5 Final 251211` and creation `2026-08-11 16:04:17`. The file fields and timestamp match only `C-4378__s-B1/shikoku.clmb` among the installed profiles. In the same sample, `CWInterface.countryCode()` returned an empty string. The `AppleBCMWLANSkywalkInterface` registry entry for `en0` published `TR` before and after the CoreWLAN sample. [Running and installed build evidence](../evidence/2026-11-17-clm-channel-tables.json), [OpenWrt creation date field](https://lxr.openwrt.org/source/firmware-utils/src/bcmclm.c#L298)

Kyushu B1 and B3 contain timestamps `2026-08-11 16:04:09` and `2026-08-11 16:05:13`. The three differing CLM dataset bytes are in those strings. Every other dataset byte, the trailing record, and both channel and code tables match. The remaining eight file-byte differences are the two updated checksums. [Byte comparison](../evidence/2026-11-17-clm-channel-tables.json), [BLOB checksum audit](clm-profile-audit.md)

## The 5,725 MHz band edge

Türkiye's BTK technical criteria place the upper edge of the 5,470 MHz Wi-Fi band at 5,725 MHz. The same document lists a separate 5,725–5,875 MHz short-range-device entry with its own requirements. The Linux regulatory database also records 5,725 MHz as the upper edge in its `TR` entry. In the stock Shikoku file, the seven opaque bytes after the `TR` code match 86 other rows, including `DE`, `FR` and `GB`. The channel recheck reproduced the earlier `TR` list. [BTK technical criteria](https://www.btk.gov.tr/uploads/pages/frekans-tahsisinden-muaf-telsiz-cihaz-ve-sistemleri-olcutler-633d4ca68c0b1.pdf?trk=public_post_comment-text), [Linux regulatory database](https://kernel.googlesource.com/pub/scm/linux/kernel/git/wens/wireless-regdb/+/refs/heads/master/db.txt#2021), [Local comparison](../evidence/2026-11-17-clm-5725-edge.json)

All three A2337 lab blocks absent from the stock list straddle that boundary. A nominal block extends half its width above and below its center.

| Width | Lab test center | Nominal span | Above the band edge |
| ---: | ---: | ---: | ---: |
| 20 MHz | 5,720 MHz (channel 144) | 5,710–5,730 MHz | 5 MHz |
| 40 MHz | 5,710 MHz (center 142) | 5,690–5,730 MHz | 5 MHz |
| 80 MHz | 5,690 MHz (center 138) | 5,650–5,730 MHz | 5 MHz |

This is an inference from the published edge and all three missing blocks. The effective stock firmware lookup from the `TR` row to each channel permission remains open. The live airtime sample's zero for 144 came with a running default-state timer and no new state entries. [Geometry and comparison](../evidence/2026-11-17-clm-5725-edge.json), [Live channel 144 observations](live-wifi-airtime.md#state-history-and-freshness)

## How the host driver gets the list

Apple documents CoreWLAN's supported-channel getter as querying the interface for the active country. In both signed AppleBCMWLAN slices, `getCurrentSupportedChannels` queries the firmware country, copies the returned country text into its `chanspecs` query, and converts returned entries with `getAppleChannelSpec`. Both the `SUPPORTED_CHANNELS` and `HW_SUPPORTED_CHANNELS` driver handlers call `getSupportedChannelsMatching`, which contains a restricted-country check, another `chanspecs` query, and reply decoding. The hardware-named handler therefore depends on a firmware channel-list request. [CoreWLAN supported channels](https://developer.apple.com/documentation/corewlan/cwinterface/supportedwlanchannels%28%29?changes=_6), [Signed driver call sites](../evidence/2026-11-17-clm-channel-tables.json)

On the country-change repopulation path the same driver requests `chanspecs` asynchronously and registers `handleGetChanSpecs` as the completion handler. That handler calls `adjustBeaconListPerNewCountryCode`. These are static code paths. The live check used the public status getters under the existing association, with channel 40 at 80 MHz and the IPv4 default route on `en0` at both snapshots. [Signed driver and stock snapshots](../evidence/2026-11-17-clm-channel-tables.json)

The reply loop in both slices converts each firmware channel specification, consults the passive and DFS checks, and applies the requested flag masks before appending the host result. The firmware's returned entries and the masks for the live host request remain to be traced. [Reply-loop call sites](../evidence/2026-11-17-clm-5725-edge.json)

## Reproduce the reads

```sh
python3 -B tools/audit_clm_channels.py --region-code TR \
  /usr/share/firmware/wifi/C-4378__s-B1/{atlantisb,capri,honshu,kyushu,santorini,shikoku}.clmb \
  /usr/share/firmware/wifi/C-4378__s-B3/kyushu.clmb
swift tools/read_wifi_status.swift
ioreg -r -d 1 -l -c AppleBCMWLANSkywalkInterface | rg '"IO80211CountryCode"'
ioreg -r -d 1 -l -c AppleBCMWLANCore | rg -A 6 '"CLMVersion"'
```
