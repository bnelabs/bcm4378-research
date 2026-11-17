# Timing and ranging diagnostics in Apple’s Wi-Fi driver

The AppleBCMWLAN DriverKit bundle from macOS 27.2.1 (26B131) passed strict code-signature verification. Both slices contain the same two TWT strings in `__TEXT,__cstring`. The strings match two labels in a 189-entry diagnostic argument table in the bundle’s Signposts plist. One PROXD label comes from the same table. Apple’s `dyld_info` reports a constant-data reference to each of the three strings in each slice. This establishes how the driver includes the labels in its diagnostic metadata. [Prior timing evidence](../evidence/2026-11-17-wifi-timing-capabilities.json), [Apple Mach-O section definitions](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/CodeFootprint/Articles/MachOOverview.html)

Each slice also contains eight FTM C strings and 26 PROXD C strings. Two PROXD diagnostic format strings have separate integer `status` and `core supported` arguments. Each template has one direct reference in `handleRangingEvent`. A follow-up trace found that the driver takes `core supported` and the core ID from the low and high bytes of a firmware event field. The recorded investigation contains no sample of that event field. [Original section and reference evidence](../evidence/2026-11-17-driver-timing-provenance.json), [Ranging initializer and live capability evidence](firmware-capabilities.md#ranging-on-the-bcm4378)

| macOS platform profiles | Parsed values | Timing or ranging markers in Data fields |
| --- | --- | ---: |
| Shikoku, Honshu and Capri | 4 integers, 2 booleans, 25 Data fields each | 0 |
| Kyushu | 4 integers, 2 booleans, 26 Data fields | 0 |

The four platform profiles have no keys matching the tested capability, clock, proximity or scheduling terms. The Data fields were searched for selected ASCII markers. Their field definitions remain unknown. The installed firmware profiles carry per-core proximity offsets. The running BCM4378 reports ranging eligibility and `proxd`. Actual FTM sessions and negotiated TWT remain unverified. [Profile structure and search coverage](../evidence/2026-11-17-driver-timing-provenance.json), [BCM4378 firmware settings](../evidence/2026-11-17-wifi-timing-capabilities.json), [Live capability evidence](../evidence/2026-11-17-live-firmware-capabilities.json)
