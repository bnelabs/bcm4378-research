# BCM4378 firmware RAM diagnostics

Linux stable `v7.3.4` and Asahi `asahi-7.3.4-2` register a device coredump callback in the BCM4378 PCIe driver. In a kernel with device coredumps enabled, the driver model can dispatch a diagnostic request to that callback. The callback copies device RAM and submits it to the device coredump subsystem. The firmware-crash handler calls the same callback and then schedules a reset. The effect of a diagnostic capture on live link timing remains unmeasured. [Linux PCIe callback registration](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L2762-L2781), [Asahi PCIe callback registration](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L3138-L3154), [Driver-model gate](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/base/dd.c#L473-L505), [Asahi diagnostic and recovery paths](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/core.c#L1447-L1476)

## Capture boundaries

The PCIe copy starts at the driver's RAM base and has length `ramsize - srsize`, where `srsize` is the reported save/restore area. The direct callback emits RAM at file offset zero. The watchdog-event handler can place event data before the same RAM range. The file's producer and event length determine where RAM byte zero lies. Coverage of separate register and D11 memories remains unverified. [PCIe copy and size](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L1661-L1680), [Watchdog payload](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/core.c#L977-L999), [Dump framing](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/debug.c#L17-L42)

The chip-identification code maps BCM4378 ARM RAM to `0x352000` and rejects initially detected sizes above 4 MiB. The separate firmware size override is absent from all three installed image payloads. The signed macOS driver declares 1,892,352 bytes of ARM RAM for the BCM4378 and uses that length for its normal fault attachment. The 8 MiB PCIe aperture is a separate mapped length. Runtime Linux bank totals and save/restore sizes remain to be measured on the bench. [macOS memory layout](chip-memory-map.md), [Asahi RAM discovery and size guard](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/chip.c#L720-L791), [RAM-size override](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L1759-L1778), [Installed inputs](../evidence/2026-11-17-ram-diagnostics.json)

## Stock text and Linux boot serialization

The two stock firmware directories contain the same 250 BCM4378 NVRAM paths and ten distinct payloads. Every payload has one space before the equals sign on the `slice/1/olpc_thresh2g` line. Both pinned trees use identical NVRAM parser code, which rejects that space while reading the key. Replaying the parser for all ten payloads confirmed that this is the only stock record it drops in either modeled platform-MAC scenario. This finding describes Linux handling of the installed text. The effect of the threshold and the value applied at runtime in macOS or Linux remain unverified. [Key parser](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/firmware.c#L110-L142), [NVRAM audit](../evidence/2026-11-17-ram-diagnostics.json)

The selected Shikoku input contains 296 assignments in 7,690 text bytes. The sizing replay matched the complete encoded bytes against an independent model in both cases. The platform-MAC case used a synthetic address.

| Shikoku case | Assignments in encoded block | Slice 1 assignments | Encoded bytes with padding and token |
| --- | ---: | ---: | ---: |
| Platform MAC absent | 295 | 46 | 7,672 |
| Platform MAC provided | 296 | 46 | 7,696 |

Asahi's loader places the flat image at RAM base and NVRAM at the top of the driver-reported RAM. The BCM4378 entry requests a 264-byte random-seed record immediately before NVRAM, including its footer. The signature sidecar is optional. The two stock roots contained zero BCM4378 `.sig` names and did contain them for BCM4388. After launch the driver waits for the top RAM word to change from its boot value to the firmware's shared-memory address. A running capture that reaches this boundary can contain the address in the word that held the boot token. [NVRAM encoder](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/firmware.c#L390-L448), [Seed and loader layout](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L1910-L2135), [Firmware requests](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L2607-L2627), [BCM4378 seed flag](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L3125-L3136)

## Compare a retained capture

Keep the producer, kernel build, firmware identity, total RAM, and save/restore size with the capture from a separately connected test device. The local comparator accepts ordinary files and emits sizes, the reference image identity, and matching-byte counts. It validates the declared capture length before comparing the uploaded extent. A prefix-free capture uses the following form.

```sh
python3 tools/compare_ram_capture.py "$capture_file" "$firmware_file" \
  --ram-bytes "$ram_bytes" --save-restore-bytes "$save_restore_bytes"
```

For a watchdog capture with known framing, supply its event length using `--prefix-bytes`. Matching bytes establish correspondence at the compared offsets. Differences need the capture's boot or runtime state for interpretation. Synthetic fixtures exercised both layouts with the installed Shikoku image, including a one-byte change and rejected length mismatches. Physical RAM remains unmeasured on the active Mac. [Comparator](../tools/compare_ram_capture.py), [Fixture results and scope](../evidence/2026-11-17-ram-diagnostics.json)

With a paired BCM4378 `THREADX TRAP INFO` log, `--threadx-timer` reads the thread record identified by the logged timer address from the retained file. The decoded fields and the test cases are documented with the [RTOS source comparison](rtos-threadx.md#use-the-public-source-to-read-a-saved-thread-record).

For the three mapped stock builds, `--threadx-list` follows the RAM thread list without needing a paired fault log. The list head comes from the shipped watchdog path, and the reader uses the reference image's digest to choose it. [Task map and usage](rtos-threadx.md#main-and-idle-tasks-in-the-stock-images)

## Compare a D11 program capture

The firmware copies the MAC program for each D11 unit from ARM RAM into that unit's program memory. To verify a D11 program on a separately managed target, use a retained file whose producer identifies it as a little-endian D11 object-memory readback of the first 90,112 bytes beginning at word zero. Preserve the unit number and the firmware ID with it. An ARM RAM capture can contain the source bytes for both units. The readback comparison checks the separate D11 program-memory range. [D11 loader trace](firmware-layout.md#d11-microcode-and-core-selection)

```sh
python3 -B tools/inspect_d11_microcode.py "$firmware_file" --readback "$d11_readback"
```

The tool compares against both stored programs and reports the first differing 32-bit word and the total number of differing words. It verified six readback fixtures made from the three stock images, identified a changed word at index 4,096 and rejected a short file. A physical readback remains to be measured. [Comparator evidence](../evidence/2026-11-17-d11-microcode-loader.json)

Pass `--board-profile` with the board's stock text file to include the configured bands for both unit numbers alongside the readback comparison. The profile parser and the readback comparison ran together with the Shikoku files and a saved unit 1 fixture. [Factory band map and command](simultaneous-dual-band.md#factory-band-assignment), [Fixture evidence](../evidence/2026-11-17-d11-band-assignment.json)

Both signed macOS driver slices have a `reportMicrocodeLockup` method. It packages a firmware event in `FirmwareEvent.bin`, copying the event's 48-byte leading structure plus the payload length it reads from offset 20. The same method passes status and reason from offsets 8 and 12 to the fault reporter. The saved event and an actual D11 program capture have separate producer information. Keep that information when preserving a fault. [Signed-driver instructions](../evidence/2026-11-17-d11-microcode-loader.json)
