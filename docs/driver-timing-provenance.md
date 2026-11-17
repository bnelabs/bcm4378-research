# Timing and ranging diagnostics in Apple’s Wi-Fi driver

The AppleBCMWLAN DriverKit bundle from macOS 27.2.1 (26B131) passed strict code-signature verification. Both slices contain the same two TWT strings in `__TEXT,__cstring`. The strings match two labels in a 189-entry diagnostic argument table in the bundle’s Signposts plist. One PROXD label comes from the same table. Apple’s `dyld_info` reports a constant-data reference to each of the three strings in each slice. This establishes how the driver includes the labels in its diagnostic metadata. [Prior timing evidence](../evidence/2026-11-17-wifi-timing-capabilities.json), [Apple Mach-O section definitions](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/CodeFootprint/Articles/MachOOverview.html)

Each slice also contains eight FTM C strings and 26 PROXD C strings. Two PROXD diagnostic format strings have separate integer `status` and `supported` arguments. Each template has one direct code reference, and both references fall in the same compiled routine in each slice. That routine also references two FTM ranging-status strings. The local check found no direct reference to the selected board names or single-instruction materialization of the selected BCM4378 identities in either routine. The source and runtime value of the `supported` argument remain unresolved. [Section and reference evidence](../evidence/2026-11-17-driver-timing-provenance.json)

| macOS platform profiles | Parsed values | Timing or ranging markers in Data fields |
| --- | --- | ---: |
| Shikoku, Honshu and Capri | 4 integers, 2 booleans, 25 Data fields each | 0 |
| Kyushu | 4 integers, 2 booleans, 26 Data fields | 0 |

The four platform profiles have no keys matching the tested capability, clock, proximity or scheduling terms. The Data fields were searched for selected ASCII markers. Their field definitions remain unknown. The installed firmware profiles carry per-core proximity offsets. Eligibility for FTM ranging or TWT on the BCM4378 remains unverified. [Profile structure and search coverage](../evidence/2026-11-17-driver-timing-provenance.json), [BCM4378 firmware settings](../evidence/2026-11-17-wifi-timing-capabilities.json)
