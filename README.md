# Broadcom BCM4378 research

This repository records the Wi-Fi hardware, driver and firmware of the 2020 M1 MacBook Air (`MacBookAir10,1`). The research started on 17 November 2026. This Mac relies on Wi-Fi for internet access, so on-host measurements use stock macOS readouts and local file analysis.

- [Hardware and capability findings](docs/findings.md) records the M1 Air baseline and model-specific lab observations.
- [Firmware layout and board selection](docs/firmware-layout.md) records the selected files, antenna and chain declarations, TxCap profiles, stored microcode candidates and the probable ARM ROM overlay map.
- [Running firmware capabilities](docs/firmware-capabilities.md) records the live firmware words and traces the macOS ranging and CSI gates.
- [Extended firmware capability parsing](docs/extended-firmware-capabilities.md) maps the signed driver's feature bits and traces the BCM4378's advertised HP2P support.
- [HP2P low-latency and transmit completion paths](docs/hp2p-low-latency.md) traces two firmware reply bits, compares three BCM4378 images, and verifies the public peer-to-peer app setting.
- [DriverKit and radio services](docs/driver-interfaces.md) records the shipped host driver, the running Wi-Fi interfaces and the Bluetooth endpoint.
- [Bluetooth companion firmware](docs/bluetooth-firmware.md) maps the controller version to installed artifacts and records the native macOS application controls.
- [Wi-Fi and Bluetooth coexistence](docs/bluetooth-coexistence-policy.md) traces board defaults, association protection and antenna-sharing telemetry.
- [Spectrum coverage and sensing](docs/spectrum-sensing.md) compares the stock channel list, A2337 lab measurements and applicable research.
- [DFS proxy and channel switches](docs/dfs-proxy-policy.md) traces the firmware gate, peer policy and laboratory channel-move measurements.
- [Clear-channel assessment reporting](docs/cca-provenance.md) traces the live legend, native cache, and Linux survey measurement.
- [A2337 RF tests](docs/a2337-rf-tests.md) records simultaneous Wi-Fi and Bluetooth tests, HE waveforms and Bluetooth transmit beamforming measurements.
- [Wi-Fi 6 resource units and trigger frames](docs/he-ofdma.md) traces the driver's OFDMA catalog and uplink control and shows how to verify allocations in an offline capture.
- [BSS coloring and spatial reuse](docs/spatial-reuse.md) traces overlapping-network mitigation, Asahi's station capability, and the reuse fields in a saved capture.
- [Wi-Fi beamforming and sounding](docs/wifi-beamforming.md) traces the firmware roles, A2337 RF tests, and the sounding and feedback fields in saved captures.
- [Wi-Fi roaming policy](docs/wifi-roaming.md) decodes the Shikoku RSSI policy inputs and verifies a capture method for Fast BSS Transition.
- [Retry limits and frame aggregation](docs/wifi-retries-and-aggregation.md) traces macOS retry and Block Ack policy, tests the Linux retry control, and measures saved captures.
- [Simultaneous dual-band policy](docs/simultaneous-dual-band.md) maps the macOS firmware and platform gates and the Linux channel and station limits.
- [Live access and control](docs/live-access.md) records the PCIe apertures, UART metadata, transmit-power readout and conditions for testing deeper controls.
- [Chip memory and backplane layout](docs/chip-memory-map.md) traces the signed driver's RAM geometry, core and wrapper regions, and normal fault attachment.
- [PCIe link and power properties](docs/pcie-link-properties.md) records the shared port, endpoint status fields, and link power capability and policy.
- [Packet timestamps and PCIe time measurement](docs/packet-timestamps.md) traces the driver's clock modes, verifies the stock macOS timestamp readouts, and compares timing fields in a saved capture.
- [Chip-delay fields and host completion latency](docs/chip-delay.md) decodes the conditional delay scales and traces the published `TxCompletion Latency` histogram.
- [Packet queues and PCIe ring sizing](docs/pcie-queue-sizing.md) traces the live scheduler and Shikoku transport settings through macOS and compares Linux descriptor depths.
- [Wi-Fi traffic scheduling](docs/wifi-traffic-scheduling.md) verifies per-socket service types and pacing settings, maps host queues, and traces WME and MSCS paths.
- [macOS host power policy](docs/host-power-policy.md) records network wake and keepalive settings and their scope.
- [Temperature, voltage, and transmit power management](docs/tvpm.md) compares the B1 board tables and traces driver requests and thermal reporting.
- [Sleep network offloads](docs/sleep-network-offloads.md) traces Wake-on-WLAN policy, address resolution, Bonjour discovery, and TCP keepalive slots.
- [Radio power and wake scheduling](docs/radio-power-scheduling.md) traces associated sleep, beacon intervals, and Target Wake Time capability evidence.
- [Radio-chain and channel-width policy](docs/radio-chain-policy.md) traces MIMO power save, spatial-stream reporting and the Linux antenna fields.
- [Linux and Asahi controls](docs/asahi-controls.md) records the versioned driver paths and readouts for a separately managed A2337.
- [Firmware RAM diagnostics](docs/ram-diagnostics.md) maps the Linux capture boundary, boot serialization, and offline comparison.
- [macOS NVRAM normalization](docs/macos-nvram-normalization.md) traces the signed driver's text conversion and the firmware's threshold-name calls.

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

Reproduce the [microcode and ROM overlay checks](docs/firmware-layout.md#microcode-build-metadata-and-record-structure), [sidecar checks](docs/firmware-layout.md#selected-radio-sidecars), and [CLM profile audit](docs/clm-profile-audit.md) with the local stock files.

## Next research questions

1. Verify D11 component selection, the destination and transfer count of the shared copy routine, and ROM overlay selection at runtime on a separate test target.
2. Compare the driver-reported link diary and raw transmit-power field with measurements from a calibrated spectrum receiver or a controlled obstruction test.
3. Verify simultaneous infrastructure and peer-to-peer transfer, and the runtime availability of the A2337's lab modes, on a separate managed test setup.
4. Compare a [driver-owned RAM capture](docs/ram-diagnostics.md) with the [declared memory geometry](docs/chip-memory-map.md) on a separately managed test Mac. Verify the bank sizing and register diagnostics on that device.
