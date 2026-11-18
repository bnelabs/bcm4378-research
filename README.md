# Broadcom BCM4378 Wi-Fi on the M1 MacBook Air

This project examines the Wi-Fi chip in the 2020 M1 MacBook Air (A2337, `MacBookAir10,1`). The measured Mac runs macOS 27.2.1 build 26B131 and Wi-Fi firmware `18.20.511.0.7.8.207` with firmware ID `01-2606388a`. Its internet connection uses `en0`. The research uses the installed binaries, stock status queries, and separately managed radio experiments where a test can interrupt service.

## Know Your Wifi

**KYW** lets two computers share a file on a local network and resume after a connection drops. The Rust desktop app also checks the router, compares channel plans, and explains the Wi-Fi hardware and settings your system exposes. [Use and build KYW](app/README.md), [Releases](https://github.com/bnelabs/bcm4378-research/releases)

```sh
./app/build.sh
open "app/dist/Know Your Wifi.app"
```

## Research

The [discovery catalog](docs/capability-catalog.md) is the complete list of processes, features, controls, and evidence covered so far. The [firmware feature index](docs/firmware-feature-index.md) lists all 90 words reported by the running firmware and the additional fields decoded in the driver.

The [practical radio applications](docs/practical-radio-applications.md) apply those findings to inspection, on-demand processing, synchronization, and recovery. The paired inspection test measures preview deadlines during an archive upload. A loopback test also interrupts the archive connection and verifies that previews continue and the upload resumes. The ranging study traces how the radio reports distance and what a moving inspection cart would need to load the right model before it arrives. [Run the paired transfer](docs/practical-radio-applications.md#test-the-direct-link-while-the-archive-is-moving), [Run the recovery test](docs/practical-radio-applications.md#resume-work-after-a-radio-fault), [Test the station prefetch idea](docs/practical-radio-applications.md#load-the-right-inspection-model-as-a-cart-approaches)

## What can I use today?

| Question | What the Mac can report or control |
| --- | --- |
| Why is Wi-Fi slow here? | Read signal, noise, channel, width, and reported link rate. The new sampler reads 98 live airtime records, including same-network airtime, overlapping networks, and interference. A sample on this Mac showed 17% average busy time, 11% overlapping-network CCA and 3% interference CCA. [Status and airtime](docs/live-wifi-airtime.md) |
| Can an app make a call or transfer behave better? | An app can request socket traffic priority or pacing. A compatible app can also opt into a direct connection with an Apple peer. [Traffic scheduling](docs/wifi-traffic-scheduling.md), [Peer interfaces](docs/driver-interfaces.md#running-wi-fi-interfaces) |
| Which channel and width can this Mac actually choose here? | Run the stock status reader below. Its reported channel numbers are the interface's current list by band and width. [Channel-list method](docs/clm-channel-tables.md#reproduce-the-reads) |
| Can the radio estimate distance to a peer? | The driver has result records for average distance and timing sample counts. An offline decoder reads them from a saved file. A live distance reading and a usable app interface remain open on this Mac. [Ranging result formats](docs/driver-timing-provenance.md#read-a-saved-distance-result) |
| How do I compare changes across macOS builds? | The inventory reader saves the chip, board, firmware ID, negotiated capabilities, and file hashes. The link and airtime readers capture timestamped radio state. [Device inventory](docs/findings.md), [Airtime sampler](docs/live-wifi-airtime.md#run-the-sampler) |

## Can I stay connected and use another channel?

**The hardware can operate on both bands together.** A2337 lab equipment measured simultaneous 2.4 GHz and 5 GHz transmission in HT20 test modes. Every installed BCM4378 board profile assigns 5 GHz to D11 unit 0 and 2.4 GHz to unit 1. The running firmware advertises `rsdb`, the flag for real simultaneous dual band. macOS uses it to check what the radio's slices can do. [Factory assignment and lab evidence](docs/simultaneous-dual-band.md)

On stock macOS, `en0` is the observed router connection. Discovery scans are a driver-managed way to check other channels. The driver has off-channel timing records for those scans. Apple's `awdl0` role supports direct peer traffic with compatible software. Sustained off-channel measurement during an internet session, a peer transfer confirmed on a different band, and two independent router connections on the single chip remain unverified on this build. The Linux source also has separate conditions for the number of channels and the number of router connections it exposes. [Modes and gates](docs/simultaneous-dual-band.md#keeping-an-internet-link-while-using-another-channel), [Interface evidence](docs/driver-interfaces.md)

You can read the firmware's channel history, byte counts and timing on each radio slice. In a passive run, the driver added records for channels 1, 6 and 11 on 2.4 GHz in the same three-second interval that `en0` sent and received traffic on 5 GHz. An app-selectable second radio channel and an on-air measurement of overlapping transfers remain open. [Live reports and sampler](docs/simultaneous-dual-band.md#24-ghz-records-during-5-ghz-traffic)

The paired-transfer test can require `awdl0` for previews and `en0` for full images. It verifies the interface used for each stream through the connection's own byte counts. Local transfer and interface reporting passed. The two-device run and the timing of transmissions on each band still need bench measurements. [Test and results](docs/practical-radio-applications.md#test-the-direct-link-while-the-archive-is-moving)

For continuous probing or a second router connection while this Mac stays online, an independent Wi-Fi radio or a second test device can take the second channel. [Bench controls and verification](docs/asahi-controls.md)

## Which frequencies are available when I travel?

The installed country-rules file lists the chip's general channels and groups the channels by region. We decoded the regional tables for 222 codes. The `TR` entry reproduces every channel and width this Mac reports. The offline tool can compare the installed entries for a destination and show which wide channels they share. [Country and channel trace](docs/clm-channel-tables.md#decode-the-country-specific-rules)

| Band | General 20 MHz center frequencies in the installed file | Widths seen on this Mac in `TR` |
| --- | --- | --- |
| 2.4 GHz | 2,412–2,472 MHz in 5 MHz steps, channels 1–13 | 20 MHz |
| 5 GHz | 5,180–5,320, 5,500–5,720, and 5,745–5,825 MHz in 20 MHz steps | 20, 40, and 80 MHz |

Türkiye's middle 5 GHz group ends at channel 140 in the file. Channel 144 is in the US and Japan file models and was tested in the A2337 lab. That channel is also part of a 40 MHz block and an 80 MHz block, so the `TR` list omits all three together. The US and Japan results are from stored files. Continuous analog tuning range and 6 GHz or 160 MHz operation remain unverified. [Regional examples](docs/clm-channel-tables.md#plan-an-access-point-before-a-field-deployment), [Lab coverage](docs/spectrum-sensing.md#a2337-lab-spectrum)

Compare the installed entries for an owned access point before travel. The tool returns center channels and their constituent primaries, along with the center channels shared by the requested regions.

```sh
python3 -B tools/audit_clm_channels.py --locale TR --locale US --locale JP \
  /usr/share/firmware/wifi/C-4378__s-B1/shikoku.clmb
```

Run these in the place where you will use the Mac. The second command reads the reported country for the active interface. Apple scopes the channel getter to that country and recommends enabling the Networking & Wireless location service to help devices connect under local channel and signal rules. [Apple's supported-channel API](https://developer.apple.com/documentation/corewlan/cwinterface/supportedwlanchannels%28%29?changes=_6), [Apple Wi-Fi settings](https://support.apple.com/en-us/102766)

```sh
swift tools/read_wifi_status.swift
ioreg -r -d 1 -l -c AppleBCMWLANSkywalkInterface | rg '"IO80211CountryCode"'
```

## Where is the firmware code?

The macOS driver requests `/usr/share/firmware/wifi/C-4378__s-B1/shikoku.trx`, which resolves to `honshu.trx`. Load that local file in a disassembler to read the Wi-Fi processor's instructions. The directory also contains the board settings, regulatory tables, and transmit-power caps. The [firmware layout](docs/firmware-layout.md#files-requested-by-the-running-driver) gives all four selected filenames and their roles.

All three installed builds contain an initialization call that prints **ThreadX 5.6**. We traced that call and a fault routine that prints thread and stack details. We also mapped the loader, selected memory ranges, parts of the radio code, and driver requests. A complete instruction-level reconstruction of the Broadcom firmware remains open. [RTOS disassembly and reproduction](docs/rtos-threadx.md)

The file also holds two **88 KiB programs for the wireless MAC cores**. We traced the exact program selected for each core and the port used to load its instruction memory. Both programs match across Honshu, Capri and Kyushu. The readback tool can show the factory band for each program and check a saved program-memory capture against either build component. [MAC programs and loader](docs/firmware-layout.md#d11-microcode-and-core-selection), [Readback tool](docs/ram-diagnostics.md#compare-a-d11-program-capture)

The [Eclipse ThreadX repository](https://github.com/eclipse-threadx/threadx) and its [releases](https://github.com/eclipse-threadx/threadx/releases) publish upstream RTOS source. Apple's local `.trx` contains the compiled device build. This repository's [tools](tools/) are our inspection and measurement code, and [evidence](evidence/) contains saved results.

## What can the chip do on its own?

The Wi-Fi processor runs its own threads and timers. macOS supplies board and network settings and exchanges packets and commands with it over PCIe. The chip can handle radio timing, frame retries, grouping, and measurements between host requests. For sleep, the driver can prepare address-resolution replies, wake filters, Bonjour records, and keepalives for established TCP connections. The firmware can execute those prepared tasks while the main processor sleeps. The awake firmware features and setup paths are verified. Actual sleep traffic still needs a synchronized capture. [How the tasks fit together](docs/rtos-threadx.md#which-tasks-can-run-on-the-chip), [Sleep network offloads](docs/sleep-network-offloads.md), [Chip-to-host queues](docs/pcie-queue-sizing.md)

The saved power history has 67 dark wakes tagged by the shared Wi-Fi and Bluetooth subsystem. The signed WLAN driver has distinct wake reasons for data arriving on a keepalive connection and for the connection timing out. The historical records leave those events unattributed to a specific packet or offload. [Decoded reasons and retained history](docs/sleep-network-offloads.md#keepalive-wake-reasons)

The signed driver has a path for attaching firmware RAM to fault diagnostics, and the Asahi driver has a device-coredump path. The ThreadX fault routine prints a timer address that locates the thread record. We added a decoder for a saved capture paired with that log. An interactive RTOS interface and full live register and RAM control remain unverified. [Thread record decoder](docs/rtos-threadx.md#use-the-public-source-to-read-a-saved-thread-record), [Memory map](docs/chip-memory-map.md), [RAM capture format](docs/ram-diagnostics.md)

## Detailed research notes

| Area | Documents |
| --- | --- |
| The hardware and transport | [Baseline](docs/findings.md), [Driver interfaces](docs/driver-interfaces.md), [PCIe link](docs/pcie-link-properties.md), [Packet queues](docs/pcie-queue-sizing.md), [Chip delay](docs/chip-delay.md), [Timestamps](docs/packet-timestamps.md) |
| Firmware and control | [Firmware layout](docs/firmware-layout.md), [Runtime capabilities](docs/firmware-capabilities.md), [Low-latency peers](docs/hp2p-low-latency.md), [Live access](docs/live-access.md), [Linux and Asahi](docs/asahi-controls.md), [Board setting normalization](docs/macos-nvram-normalization.md) |
| Radio behavior | [Spectrum](docs/spectrum-sensing.md), [A2337 lab results](docs/a2337-rf-tests.md), [CCA event path](docs/cca-provenance.md), [DFS](docs/dfs-proxy-policy.md), [Roaming](docs/wifi-roaming.md), [Chain and width policy](docs/radio-chain-policy.md) |
| Wi-Fi performance | [Wi-Fi 6 scheduling](docs/he-ofdma.md), [Spatial reuse](docs/spatial-reuse.md), [Beamforming](docs/wifi-beamforming.md), [Retries and aggregation](docs/wifi-retries-and-aggregation.md), [Traffic priority](docs/wifi-traffic-scheduling.md) |
| Power and Bluetooth | [Host power policy](docs/host-power-policy.md), [Radio wake scheduling](docs/radio-power-scheduling.md), [Thermal and power limits](docs/tvpm.md), [Bluetooth firmware](docs/bluetooth-firmware.md), [Wi-Fi and Bluetooth coexistence](docs/bluetooth-coexistence-policy.md) |

## Reproduce the baseline

From the repository root, run the firmware inspection with Python 3. It reads the specified local files and emits JSON.

```sh
python3 tools/inspect_firmware.py \
  /usr/share/firmware/wifi/C-4378__s-B1/shikoku.trx \
  --platform-config /usr/share/firmware/wifi/shikoku-PlatformConfig.plist
```

On macOS with Swift installed, query the current connection using CoreWLAN getters.

```sh
swift tools/read_wifi_status.swift
swift tools/read_wifi_status.swift --sample 16 0.5
swift tools/read_wifi_status.swift --sample 36 1 | python3 tools/summarize_link.py
swift tools/read_wifi_status.swift --sample 21 0.5 --traffic | python3 tools/summarize_link.py
python3 tools/summarize_link.py --he-candidates evidence/2026-11-17-link-activity-sample.json
python3 tools/read_link_role_counters.py --samples 46 --interval 1
python3 tools/read_macos_inventory.py
swift tools/read_pcie_link.swift
```

The sampler emits timestamped JSON lines from the current association's status getters. The summary reports missing and repeated readings, operating context, PHY rate and paired RSSI-minus-noise. The optional `--traffic` flag adds aggregate interface byte and packet counts. The `--thermal` flag adds the public host thermal state. The offline `--he-candidates` option lists compatible nominal HE modes for each reported whole-Mb/s rate under a full-channel model. The role-counter tool compares host counter changes across five Wi-Fi interfaces in the same time windows. The inventory records I/O Registry role names, PCIe aperture sizes, published firmware capability words and coexistence parameters, and hashes of the selected firmware files.

```sh
python3 tools/inventory_board_profiles.py /usr/share/firmware/wifi
python3 tools/compare_firmware.py \
  /usr/share/firmware/wifi/C-4378__s-B1/honshu.trx \
  /usr/share/firmware/wifi/C-4378__s-B1/capri.trx \
  /usr/share/firmware/wifi/C-4378__s-B3/kyushu.trx
```

Reproduce the [microcode and ROM overlay checks](docs/firmware-layout.md#microcode-build-metadata-and-record-structure), [sidecar checks](docs/firmware-layout.md#selected-radio-sidecars), [CLM profile audit](docs/clm-profile-audit.md), and [channel-table audit](docs/clm-channel-tables.md#reproduce-the-reads) with the local stock files.

## Next research questions

1. Verify the program loaded into each D11 unit and the active ROM overlays on a separately managed test target. The stock code now identifies both D11 sources and their destination. [D11 loader](docs/firmware-layout.md#d11-microcode-and-core-selection)
2. Compare the driver-reported link diary and raw transmit-power field with measurements from a calibrated spectrum receiver or a controlled obstruction test.
3. Verify simultaneous infrastructure and peer-to-peer transfer, and the runtime availability of the A2337's lab modes, on a separate managed test setup.
4. Compare a [driver-owned RAM capture](docs/ram-diagnostics.md) with the [declared memory geometry](docs/chip-memory-map.md) on a separately managed test Mac. Verify the bank sizing and register diagnostics on that device.
