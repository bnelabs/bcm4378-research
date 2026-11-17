# The operating system inside the BCM4378

The installed BCM4378 firmware contains an initialization call that prints **ThreadX 5.6**. All three distinct shipped executables pass integer arguments 5 and 6 to the same version message. The running registry identifies firmware `18.20.511.0.7.8.207`, FWID `01-2606388a`, and requests `shikoku.trx`. That filename resolves to `honshu.trx`. The version announcement was decoded offline from that executable and the two other builds. [Image identities and instruction evidence](../evidence/2026-11-17-threadx-firmware.json), [File selection](firmware-layout.md#files-requested-by-the-running-driver)

ThreadX is the small real-time operating system that schedules work on the Wi-Fi chip's embedded processor. Its upstream source is public. The Apple/Broadcom build on this Mac is shipped as compiled machine code, including board-specific WLAN, PCIe, and radio work. The upstream source helps recognize the RTOS's scheduling and thread structures. A full reconstruction of the shipped image remains open. [Eclipse ThreadX source](https://github.com/eclipse-threadx/threadx), [Firmware byte map](firmware-layout.md#byte-reuse-across-images)

## Find the executable and read the instructions

The requested Apple file is `/usr/share/firmware/wifi/C-4378__s-B1/shikoku.trx`. The installed build used below is `/usr/share/firmware/wifi/C-4378__s-B1/honshu.trx`. Board settings, country data, and transmitter caps are separate files. The public Asahi/Linux loader copies the flat image into device RAM. Its `0x352000` model is the reference mapping for the disassembly. [Loader evidence](firmware-layout.md#reference-loading-model)

```sh
python3 tools/inspect_firmware.py /usr/share/firmware/wifi/C-4378__s-B1/honshu.trx
rizin -N -q -a arm -b 16 -m 0x352000 \
  -c 'pd 14 @ 0x3b02e0' /usr/share/firmware/wifi/C-4378__s-B1/honshu.trx
```

| Executable | Version format load | Version print call | Thread fault-report banner load |
| --- | --- | --- | --- |
| B1 Honshu | `0x3b02ea` | `0x3b02ec` | `0x3b20d8` |
| B1 Capri | `0x3b02ea` | `0x3b02ec` | `0x3b20d8` |
| B3 Kyushu | `0x398b86` | `0x398b88` | `0x39a1b8` |

The format pointer is loaded into ARM register `r0`, and the startup code puts 5 in `r1` and 6 in `r2`. Those are the first two arguments after the format string. Honshu and Kyushu also load fault formats for the thread name, ID, run count, stack bounds and size, thread entry function, and timer. The addresses above are offline disassembly coordinates under the reference mapping. A live boot or fault capture remains to be collected on a separate target. [Call sites and file hashes](../evidence/2026-11-17-threadx-firmware.json)

## Use the public source to read a saved thread record

The upstream release list examined has 28 entries, starting at `v6.0_rel`. Its `v6.5.2.202603b_rel` headers expose the thread control-block fields in the order used by the stock fault routine. With 32-bit words and an empty first port extension, the relevant positions agree with the firmware's observed offsets. [Eclipse release list](https://github.com/eclipse-threadx/threadx/releases), [Pinned TX_THREAD definition](https://github.com/eclipse-threadx/threadx/blob/v6.5.2.202603b_rel/common/inc/tx_api.h#L423-L473), [Instruction and release checks](../evidence/2026-11-17-threadx-firmware.json)

| Offset from thread record | Field printed by the firmware |
| ---: | --- |
| `0x00`, `0x04` | Thread ID and run count |
| `0x08`, `0x0c`, `0x10`, `0x14` | Stack pointer, start, end, and size |
| `0x28` | Thread name pointer |
| `0x44` | Thread entry function pointer |
| `0x4c` | Address of the embedded timer printed as `Timer` |

The timer address ties a fault log to a particular thread record. With the log and a retained main-RAM capture from the same fault, the comparator derives the record address and prints the fields from the file. Provide the capture layout as reported by its producer. The decoder checks the public control-block ID `0x54485244` and reports a name when the string is present in the capture. The decoder passed synthetic raw and event-prefixed capture tests. A field capture remains open. [RAM capture layout](ram-diagnostics.md#capture-boundaries), [Upstream ID definition](https://github.com/eclipse-threadx/threadx/blob/v6.5.2.202603b_rel/common/inc/tx_thread.h#L44), [Comparator](../tools/compare_ram_capture.py)

```sh
python3 tools/compare_ram_capture.py "$capture_file" "$firmware_file" \
  --ram-bytes "$ram_bytes" --save-restore-bytes "$save_restore_bytes" \
  --prefix-bytes "$prefix_bytes" --threadx-timer "$timer_address"
```

## Which tasks can run on the chip

macOS supplies the firmware image, board inputs, network state, and requested work. DriverKit and the radio exchange control messages, packet descriptors, and completions over PCIe. The embedded processor can schedule its own threads and handle radio work while the main processor is doing something else. The host configures the operating state and the tasks it hands to firmware. [PCIe packet and control path](pcie-queue-sizing.md), [ThreadX scheduler source](https://github.com/eclipse-threadx/threadx)

| When | Work found in the stock chip and driver paths |
| --- | --- |
| Normal connection | Radio-side rate and retry work, aggregation, channel-busy measurement and events. The host posts packets and consumes completions and reports. [Retries and aggregation](wifi-retries-and-aggregation.md), [Airtime](live-wifi-airtime.md) |
| The link enters power save | The radio can follow beacon wake timing and associated sleep policy. The live execution of an accepted Target Wake Time schedule remains unmeasured. [Radio power scheduling](radio-power-scheduling.md) |
| macOS prepares for sleep | The driver can provision IPv4 ARP and IPv6 neighbor responses, wake filters, selected Bonjour records, and keepalive frames for existing TCP flows. Those prepared operations can run between host wakeups. The current evidence establishes the capability response and programming path. Exact sleep traffic and responses from this Mac remain unmeasured. [Sleep offload evidence](sleep-network-offloads.md) |

These mechanisms explain how a chip can transmit or respond without a user action or a new host request for each frame. Their scope comes from the radio firmware and the network and sleep policy programmed by the host.

## How much runtime access is verified

The signed macOS driver has a driver-owned fault attachment for 1,892,352 bytes of ARM firmware RAM. The reviewed Asahi driver has a device-coredump path that reads its reported RAM range, with save/restore memory handled separately. A retained dump from an independently managed device can be searched for thread state and compared with the shipped bytes. A verified interactive RTOS console, a complete map of live memory, and a custom firmware load under owner control remain open. [Apple memory map](chip-memory-map.md), [Retained diagnostic format](ram-diagnostics.md)
