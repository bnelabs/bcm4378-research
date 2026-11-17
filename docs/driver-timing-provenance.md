# Timing and ranging diagnostics in Apple’s Wi-Fi driver

The AppleBCMWLAN DriverKit bundle from macOS 27.2.1 (26B131) passed strict code-signature verification. Both slices contain the same two TWT strings in `__TEXT,__cstring`. The strings match two labels in a 189-entry diagnostic argument table in the bundle’s Signposts plist. One PROXD label comes from the same table. Apple’s `dyld_info` reports a constant-data reference to each of the three strings in each slice. This establishes how the driver includes the labels in its diagnostic metadata. [Prior timing evidence](../evidence/2026-11-17-wifi-timing-capabilities.json), [Apple Mach-O section definitions](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/CodeFootprint/Articles/MachOOverview.html)

Each slice also contains eight FTM C strings and 26 PROXD C strings. Two PROXD diagnostic format strings report separate `status` and `core supported` values. The driver takes `core supported` and the core ID from the low and high bytes of a firmware event field. A six-hour search of retained logs yielded one rendered PROXD session status with state 9, status 0, burst number 4, `core supported` 0 and core ID 0. The same search yielded zero rendered distance or burst status logs. This event records the session state. The initiating feature, operating band, result distance and meaning of the zero in this session remain open. [Original section and reference evidence](../evidence/2026-11-17-driver-timing-provenance.json), [Retained log counts and fields](../evidence/2026-11-17-ranging-results.json)

| macOS platform profiles | Parsed values | Timing or ranging markers in Data fields |
| --- | --- | ---: |
| Shikoku, Honshu and Capri | 4 integers, 2 booleans, 25 Data fields each | 0 |
| Kyushu | 4 integers, 2 booleans, 26 Data fields | 0 |

The four platform profiles have no keys matching the tested capability, clock, proximity or scheduling terms. The Data fields were searched for selected ASCII markers. Their field definitions remain unknown. The installed firmware profiles carry per-core proximity offsets. The running BCM4378 reports ranging eligibility and `proxd`. Actual FTM sessions and negotiated TWT remain unverified. [Profile structure and search coverage](../evidence/2026-11-17-driver-timing-provenance.json), [BCM4378 firmware settings](../evidence/2026-11-17-wifi-timing-capabilities.json), [Live capability evidence](../evidence/2026-11-17-live-firmware-capabilities.json)

## Read a saved distance result

Both signed slices of the macOS 26B131 driver parse three distance result layouts in `AppleBCMWLANCore::handleRangingEvent`. For class 5, the event payload starts at offset `0x30`. The driver reads the first type at event offset `0x3c` and the value starts at `0x40`. Its three length checks use the event's available bytes after that header. The table uses offsets from the start of the value. [Instruction addresses in both slices](../evidence/2026-11-17-ranging-results.json)

| Type | Diagnostic version | Minimum available value bytes | Session ID offset | Averaged distance offset |
| --- | --- | ---: | ---: | ---: |
| `0x203` | 1 | 128 | `0x00` | `0x44` |
| `0x208` | 2 | 96 | `0x04` | `0x1c` |
| `0x209` | 3 | 44 | `0x04` | `0x1c` |

The flags, status and state are at session offsets `+0x02`, `+0x04` and `+0x0e`. The valid sample count, Fine Timing Measurement frame count, burst number and round-trip sample count are at distance offsets `+0x06`, `+0x07`, `+0x08` and `+0x0a`. The corresponding log arguments identify the four fields. Bytes between the status and state hold the peer address and are omitted by the decoder. [Result and log references](../evidence/2026-11-17-ranging-results.json)

The average distance field represents units of 1/256 metre, about 3.9 mm per stored increment. Physical accuracy needs a measured reference distance. The driver conditionally negates the version 2 word when flag `0x80` is set. All three paths multiply the signed word by 1,000, check that the product fits a signed 32-bit integer, and shift right by eight before storing the result as a float. The decoder preserves the raw word, reports both the represented distance and the driver's integer millimetre conversion, and recognizes `0xffffffff` as unavailable following Broadcom's published host code. [Apple conversion evidence](../evidence/2026-11-17-ranging-results.json), [Broadcom distance format and sentinel](https://android.googlesource.com/kernel/google-modules/wlan/bcmdhd/bcm4383/+/3b1a081640892e16ac658f66a0b0d026735922fe/dhd_rtt.c#4426)

```sh
python3 -B tools/inspect_ranging_result.py saved-result.bin
```

Provide a single saved record with a little-endian 16-bit type, a 16-bit value length, and the value. The decoder accepts optional padding to the next four-byte boundary. It passed 12 synthetic CLI cases covering the three versions, sign and scaling, malformed records, padding, overflow, and the unavailable marker. A retained distance value from an actual BCM4378 exchange is still needed to test it against hardware. [Decoder](../tools/inspect_ranging_result.py), [Fixture results](../evidence/2026-11-17-ranging-results.json), [Broadcom alignment](https://android.googlesource.com/kernel/common/+/bcmdhd-3.10/drivers/net/wireless/bcmdhd/bcmxtlv.c)

## What the stock calibration changes

All 250 installed BCM4378 NVRAM names contain `proxd_seq_2g_rx_win_adj=1` and matching four-entry `proxd_seq_2g_kval_chan_offset_core0` and `core1` arrays. The arrays are `0,150,0,0` on AtlantisB, Honshu, Kyushu and Shikoku and `0,50,0,0` on Capri and Santorini. The same test counted zero profiles with the corresponding two 5 GHz keys. [Calibration inventory](../evidence/2026-11-17-ranging-results.json)

The Honshu and Capri Thumb loaders begin fetching the 2.4 GHz keys at `0x4659f0`. Kyushu B3 does the same at `0x4243c4`. Each loader calls a helper below the downloaded image for four indexed values per key and sign-extends the returned 16-bit entries into the context at `+0x234` and `+0x244`. The preceding 5 GHz loops fill `+0x214` and `+0x224`. The helper's default behavior, the offsets' units and the channels associated with each index remain open. [Thumb instructions and string pointers](../evidence/2026-11-17-ranging-results.json)

All three builds store the return for `proxd_seq_2g_rx_win_adj` at context offset `+0x255`. In both B1 builds the constructor registers the callback at `0x3a2310` with the same context. The callback reads that byte and chooses between two 20-byte templates on a path where the channel's band bits are 2.4 GHz. The corresponding B3 callback pointer falls below the downloaded image. Comparing multiple boards at the same physical distance can test for a repeatable measurement bias without editing their calibration. [Callback and template addresses](../evidence/2026-11-17-ranging-results.json), [Broadcom channel band encoding](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/include/brcmu_d11.h#L627-L637)
