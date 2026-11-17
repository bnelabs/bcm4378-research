# macOS NVRAM normalization and BCM4378 threshold names

The signed AppleBCMWLAN DriverKit executable on macOS build 26B131 includes matching normalization and validation logic in its `arm64e` and `arm64e.x1` slices. The trace used Mach-O symbols, literal loads and branches in the shipped file. The running WLAN service reported the same Shikoku image and text profile during a read-only registry sample. [Host and request evidence](../evidence/2026-11-17-macos-nvram-normalization.json), [Apple Mach-O section documentation](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/CodeFootprint/Articles/MachOOverview.html)

## Host processing

`generateChipImage` invokes `normalizeNVRAM` before generating the provisioned records. For the printable stock text, `getNormalizedNVRam` skips leading spaces, collapses repeated spaces and removes a trailing space at record termination. It copies one interior space and copies the following equals sign as an ordinary byte. In the line whose key is `slice/1/olpc_thresh2g` followed by one space, the space therefore survives. The provisioned-parameter routine adds calibration and MAC records and moves the normalized range as a block. Separately, `validateChipImage` invokes a checker that tests leading and repeated whitespace, line feeds and terminating NUL bytes. A single interior space passes those checks. [Driver instruction survey](../evidence/2026-11-17-macos-nvram-normalization.json)

The normalizer also removes records whose text starts with `macaddr`, `nocrc`, `il0macaddr`, `nvramver` or `moduleid`. The ten distinct stock payloads contain none of those prefixes. On those payloads the model changes each LF to NUL and adds one final NUL. For the selected Shikoku file, that yields **296 records and 7,691 bytes** before device provisioning. The pinned Linux parser keeps 295 of the original records because it rejects the space while reading the key. [Host-stage model](../tools/audit_macos_nvram_text.py), [Linux parser replay](ram-diagnostics.md#stock-text-and-linux-boot-serialization)

The driver contains debug paths for publishing the source and normalized NVRAM. The 98-entry WLAN registry sample exposed zero instances of either property. The Shikoku byte count is a model of the signed normalizer on the requested file. The bytes delivered to the chip and the active calibration remain unverified. [Registry evidence](../evidence/2026-11-17-macos-nvram-normalization.json)

## Firmware calls and stock spelling

All three distinct installed images load the four names below into the same argument register. In each image the four calls go to one common helper. Rizin independently decoded the Thumb literal loads and calls under the reference Linux load model. The separate `slice/1/` literal goes to a different helper. The table shows how the ten distinct text profiles spell the matching assignments. [Firmware and profile evidence](../evidence/2026-11-17-macos-nvram-normalization.json), [Reference load model](firmware-layout.md#reference-loading-model)

| Firmware call argument | Key spelling in each stock text payload |
| --- | --- |
| `olpc_thresh2g` | `slice/1/olpc_thresh2g` followed by one space |
| `olpc_thresh5g` | `olpc_thresh5g` |
| `olpc_anchor2g` | `slice/1/olpc_anchor2g` |
| `olpc_anchor5g` | `olpc_anchor5g` |

Both helper destinations fall below the uploaded image in the Linux mapping and outside the recorded candidate ROM-overlay rows. The available bytes leave the helpers' namespace matching and whitespace rules unresolved. The driver-owned RAM capture described for Linux starts at the uploaded RAM base. Confirming the applied setting still needs a device-side observation. [Candidate ROM overlay map](firmware-layout.md#arm-rom-overlay-map), [RAM capture boundary](ram-diagnostics.md#capture-boundaries)

## Reproduce the stock-text comparison

```sh
python3 tools/audit_macos_nvram_text.py /usr/share/firmware/wifi
```

The tool takes the retained printable, LF-terminated assignment form seen in these profiles. It outputs payload identities, modeled byte and record counts, and exact key presence. Use those fields to compare host preprocessing when evaluating calibration on a separate test device.
