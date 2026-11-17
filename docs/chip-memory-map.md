# BCM4378 memory layout in the Apple PCIe driver

The signed AppleBCMWLAN DriverKit extension from macOS 27.2.1 build 26B131 declares **1,892,352 bytes (1,848 KiB)** of ARM firmware RAM for the BCM4378. Both binary slices use that value for image allocation and the normal SoC RAM fault attachment. The active Mac's I/O Registry separately reports 64 KiB and 8 MiB PCIe apertures. The artifact trace gives the driver's RAM geometry. A physical bank count and the running RAM contents remain unmeasured. [Driver and registry evidence](../evidence/2026-11-17-bcm4378-chip-memory-map.json), [Apple PCI device provider](https://developer.apple.com/documentation/pcidriverkit/iopcidevice)

## Memory descriptors

`AppleBCMWLANChipManagerPCIe4378::initWithChip` supplies seven 12-byte memory descriptors. The table stores each region's selector, base and length. `getRAMSize` selects row 4 and returns its length. `AppleBCMWLANChipMemory::readRAM` also selects row 4. `allocChipImage` uses the same length when checking the image ranges. The row starts at the BCM4378 ARM RAM base in the pinned Linux driver. The Vinix project independently found the same base and size in the Apple driver on build 25D771280a. [Local table and instruction trace](../evidence/2026-11-17-bcm4378-chip-memory-map.json), [Linux RAM base](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/chip.c#L736-L751), [Earlier Apple driver comparison](https://github.com/vlang/vinix/blob/63fc675f13718e5724bfeac54431344815be5085/docs/apple-wifi.md#L86-L88)

| Driver selector | Length | Verified relationship or consumer |
| ---: | ---: | --- |
| 0 | 3,399,680 bytes (3,320 KiB) | `readCoexRAM` uses this view. Its declared length equals the sum of rows 1 and 4. |
| 1 | 1,507,328 bytes (1,472 KiB) | Shares its base with rows 0 and 2. Rows 2 and 3 cover this interval. |
| 2 | 32 bytes | Prefix of row 1. Selected by the driver's `writeFLOP32` helper. |
| 3 | 1,507,296 bytes | Remaining interval of row 1. |
| 4 | 1,892,352 bytes (1,848 KiB) | ARM firmware RAM. Rows 5 and 6 cover this interval. |
| 5 | 712,704 bytes (696 KiB) | First part of row 4. |
| 6 | 1,179,648 bytes (1,152 KiB) | Contiguous second part of row 4. |

The overlaps make a sum of all seven lengths unsuitable as a capacity figure. The two contiguous RAM part descriptors establish the driver's partition of the interval. The live firmware allocation within that interval remains open. [Partition checks](../evidence/2026-11-17-bcm4378-chip-memory-map.json)

## Core and wrapper regions

The chip initializer also supplies nine core register descriptors and 17 wrapper descriptors. Each describes a 4 KiB region. The separate backplane table defines four fixed windows, two remappable core windows and two remappable wrapper windows. The PCIe attach path constructs separate backplane and chip-memory objects. These counts describe the signed driver's access layout. [Driver evidence](../evidence/2026-11-17-bcm4378-chip-memory-map.json), [PCIe aperture observation](live-access.md)

| Logical core selector | Named driver consumer |
| ---: | --- |
| 0 | ChipCommon |
| 1 | MAC |
| 2 | ARM |
| 3 | PCIe |
| 6 | Global Coexistence Interface (GCI) |
| 7 | Power Management Unit (PMU) |
| 8 | OTP selection in the BCM4378 initializer |

The wrapper table includes separate sets selected by the primary and auxiliary D11 wrapper methods. The microcode scratch and shared-memory diagnostic size getters return 128 and 252, respectively. The readers have separately stored iteration bounds. Their hardware path can change device sleep state and select a D11 window before collecting data. The ARM firmware's loader also uses the core's object port to transfer 88 KiB of program bytes per unit. The physical D11 enumeration and full microcode memory sizes remain open. [Named selector and diagnostic evidence](../evidence/2026-11-17-bcm4378-chip-memory-map.json), [D11 program-memory port](firmware-layout.md#d11-microcode-and-core-selection)

## Fault attachment and Linux comparison

The authenticated call targets of `attachSoCRAMFile` lead to `getSoCRAMSize` and `readSoCRAM`. With the logging and chip-access checks satisfied, the function allocates the declared ARM RAM length and requests the normal RAM read from its beginning. The driver attaches the resulting buffer as `SoC_RAM.bin`. The expected payload length before report packaging is 1,892,352 bytes. The first five minutes of the retained boot log contained zero matching RAM layout or capture records. The scoped diagnostic directory search found zero matching filenames. [Fault path and retained observations](../evidence/2026-11-17-bcm4378-chip-memory-map.json)

The pinned Linux and Asahi drivers discover sizes from memory banks. Their SYSMEM paths differ. Stable uses a single bank count and starts at bank zero. Asahi uses revision-specific RAM and ROM counts and skips the ROM banks before totaling RAM. A retained Linux capture should be validated against its own driver-reported RAM and save/restore lengths. The Apple size gives a separate reference point for detecting an unexpected result on a managed A2337 bench. [Stable SYSMEM discovery](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/chip.c#L657-L708), [Asahi SYSMEM correction](https://github.com/AsahiLinux/linux/commit/d456705a5929ed2183360aeb384e63bcf0ef0cff), [Retained capture comparison](ram-diagnostics.md#compare-a-retained-capture)

## Reproduce the table extraction

```sh
python3 tools/inspect_macos_chip_memory.py \
  /System/Library/DriverExtensions/com.apple.DriverKit-AppleBCMWLAN.dext/com.apple.DriverKit-AppleBCMWLAN
```

The inspector reads the specified Mach-O file and uses the Xcode disassembler to locate the tables in each slice. It outputs lengths and overlap checks derived from the file. The I/O Registry observation can be repeated with the existing inventory tool. [Offline inspector](../tools/inspect_macos_chip_memory.py), [Registry reader](../tools/read_macos_inventory.py)
