# Broadcom BCM4378 research

This repository records the Wi-Fi hardware, driver and firmware of the 2020 M1 MacBook Air (`MacBookAir10,1`). The research started on 17 November 2026. This Mac relies on Wi-Fi for internet access, so on-host measurements use stock macOS readouts and local file analysis.

- [Hardware and capability findings](docs/findings.md) covers the driver services, PCIe link, firmware and published radio tests.
- [Live register and RAM access](docs/live-access.md) documents what the running Mac exposes and the separate test setup needed for deeper access.
- [Firmware evidence](evidence/2026-11-17-firmware.json) contains the hashes, embedded build tag and selected firmware and platform-config observations.

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
```

## Next research questions

1. Identify the firmware's load layout and classify the regions around the initial branch block using the on-disk image.
2. Compare the BCM4378 B1 firmware variants to identify which behaviors are common and which board-specific settings differ.
3. Establish which of the driver’s Wi-Fi Aware, SoftAP and low-latency services have a supported runtime interface on this model.
4. Evaluate driver-owned register and RAM diagnostics on a separate, independently managed test Mac.
