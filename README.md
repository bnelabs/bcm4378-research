# Broadcom BCM4378 research

This repository records the Wi-Fi hardware, driver and firmware of the 2020 M1 MacBook Air (`MacBookAir10,1`). The research started on 17 November 2026. This Mac relies on Wi-Fi for internet access, so on-host measurements use stock macOS readouts and local file analysis.

- [Hardware and capability findings](docs/findings.md) records the M1 Air baseline and model-specific lab observations.
- [Firmware layout and board selection](docs/firmware-layout.md) records the selected files, antenna and chain declarations, TxCap profiles, stored microcode candidates and the probable ARM ROM overlay map.
- [DriverKit and radio services](docs/driver-interfaces.md) records the shipped host driver, the running Wi-Fi interfaces and the Bluetooth endpoint.
- [Bluetooth companion firmware](docs/bluetooth-firmware.md) maps the controller version to installed artifacts and records the native macOS application controls.
- [Spectrum coverage and sensing](docs/spectrum-sensing.md) compares the stock channel list, A2337 lab measurements and applicable research.
- [Live access and control](docs/live-access.md) records the PCIe apertures, UART metadata, transmit-power readout and conditions for testing deeper controls.
- [Linux and Asahi controls](docs/asahi-controls.md) records the versioned driver paths and readouts for a separately managed A2337.

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
python3 tools/read_macos_inventory.py
```

The sampler emits timestamped JSON lines from the current association's status getters. The summary reports missing and repeated readings, operating context, PHY rate and paired RSSI-minus-noise. The optional `--traffic` flag adds aggregate interface byte and packet counts. The inventory records I/O Registry role names, PCIe aperture sizes and hashes of the selected firmware files.

```sh
python3 tools/inventory_board_profiles.py /usr/share/firmware/wifi
python3 tools/compare_firmware.py \
  /usr/share/firmware/wifi/C-4378__s-B1/honshu.trx \
  /usr/share/firmware/wifi/C-4378__s-B1/capri.trx \
  /usr/share/firmware/wifi/C-4378__s-B3/kyushu.trx
```

Reproduce the [microcode and ROM overlay checks](docs/firmware-layout.md#microcode-build-metadata-and-record-structure) and the [sidecar checks](docs/firmware-layout.md#selected-radio-sidecars) with the local stock files.

## Next research questions

1. Verify the D11 transfer counts, treatment of trailing zero records and ROM overlay selection at runtime on a separate test target.
2. Compare the driver-reported link diary and raw transmit-power field with measurements from a calibrated spectrum receiver or a controlled obstruction test.
3. Verify simultaneous infrastructure and peer-to-peer transfer, and the runtime availability of the A2337's lab modes, on a separate managed test setup.
4. Evaluate driver-owned register and RAM diagnostics on a separate, independently managed test Mac.
