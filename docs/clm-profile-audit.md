# BCM4378 Country Locale Matrix profiles

Both installed firmware directories contain the same 35 board-relative `.clmb` names and byte contents. B1 has six distinct payloads, and B3 has one. Each payload has a base name and four symlinks with `-ID`, `-X0`, `-X2` and `-X3` suffixes. All 35 names resolved in both directories. Asahi's firmware collector maps Apple's `.clmb` extension to Linux's `.clm_blob`. [Audit results](../evidence/2026-11-17-clm-profile-audit.json), [Asahi collector](https://github.com/AsahiLinux/asahi-installer/blob/main/asahi_firmware/wifi.py#L28-L34)

Each file has a 60-byte Broadcom `BLOB` header, a contiguous `CLM DATA` dataset and a four-byte record at the end. The audit verified the header CRC32 and both record CRC32s for all seven payloads. The four-byte record matches across all profiles and shares a digest with the trailer recorded in the TxCap inventory. Its purpose remains open. [OpenWrt BLOB layout and validation](https://github.com/openwrt/firmware-utils/blob/master/src/bcmblob.c#L195-L269), [TxCap inventory](../evidence/2026-11-17-txcap-profiles.json)

All seven datasets identify compiler `1.72.1` and import `ClmImport: 1.74.1`. Their bytes after the 104-byte CLM header yield seven distinct digests. The last column reproduces the release text as stored in the header field OpenWrt calls `manufacturer`. [OpenWrt CLM header](https://github.com/openwrt/firmware-utils/blob/master/src/bcmclm.c#L39-L50), [Audit results](../evidence/2026-11-17-clm-profile-audit.json)

| Profile | Stepping | File bytes | Dataset bytes | Release text |
| --- | --- | ---: | ---: | --- |
| AtlantisB | B1 | 34,061 | 33,997 | `v5 Final 251211` |
| Capri | B1 | 34,381 | 34,317 | `v5 EVT 251211` |
| Honshu | B1 | 36,949 | 36,885 | `v4 Final 251211` |
| Kyushu | B1 | 36,765 | 36,701 | `v2 Final 260429` |
| Santorini | B1 | 34,581 | 34,517 | `v5 EVT 251211` |
| Shikoku | B1 | 35,973 | 35,909 | `v5 Final 251211` |
| Kyushu | B3 | 36,765 | 36,701 | `v2 Final 260429` |

The Kyushu B1 and B3 datasets share their complete 104-byte header and a 36,603-byte prefix. The three differing dataset bytes are characters in the creation timestamp. The eight other file differences are four bytes of the BLOB header CRC and four of the dataset record CRC. The trailing record matches. [Kyushu comparison](../evidence/2026-11-17-clm-profile-audit.json), [Creation timestamp decode](clm-channel-tables.md#region-codes-and-profile-identity)

```sh
python3 -B tools/audit_clm_profiles.py /usr/share/firmware/wifi \
  /System/Library/DriverExtensions/com.apple.DriverKit-AppleBCMWLAN.dext/Firmware
```
