# BCM4378 temperature, voltage, and transmit power management

This A2337's running firmware advertises `tvpm`. The live driver publishes labels for radio temperature, battery voltage, transmit duty cycle, power backoff, and active chains under Temperature Voltage Power Management (TVPM). Foundation reported `nominal` in four samples taken alongside the active Wi-Fi link. Actual radio temperature, voltage, and applied limits remain unmeasured. [Foundation thermal state](https://developer.apple.com/documentation/foundation/processinfo/thermalstate-swift.enum), [Live evidence](../evidence/2026-11-17-tvpm.json)

## Installed BCM4378 B1 board policy

The driver's `RequestedFiles` property selects the Shikoku X3 RASP NVRAM file. Its alias resolves to `P-shikoku_M-RASP_V-m__m-6.11.txt`. The installed driver-bundle and shared copies match. The shared B1 directory contains 240 named `.txt` paths, of which 192 are symlinks. The 48 canonical paths have 10 distinct file hashes and two distinct sets of TVPM and selected temperature declarations. [Selected file and catalog counts](../evidence/2026-11-17-tvpm.json), [Board selection](firmware-layout.md)

| Declaration present in all 48 canonical paths | Raw value |
| --- | --- |
| `tvpm_pwrboff_temp_threshold` | `60` |
| `tvpm_dc_temp_threshold` | `85` |
| `tvpm_pwrboff_vbat_threshold`, `tvpm_dc_vbat_threshold` | `0` for both |
| `tvpm_monitor_period` | `1` |
| `tvpm_pwrboff_5g` | `4,4,4,0,0,0` |
| `tvpm_dc_vbat_temp` | `50,50,50,100,100,100,100,100,100,100,100,100` |
| `tvpm_txchain_vbat` | `0,2` |
| `phycal_tempdelta`, `rawtempsense`, `tempoffset`, `temps_hysteresis` | `15`, `0x1ff`, `255`, `0xf` |

| Declaration that differs | Shikoku, Honshu, Atlantisb, and Kyushu (30 canonical paths) | Capri and Santorini (18 canonical paths) |
| --- | --- | --- |
| `tvpm_pwrboff_2g` | `2,2,2,0,0,0` | `4,4,4,0,0,0` |
| `tvpm_dc_ppm` | `100,100,75,75,1,50` | `1,100` |
| `tvpm_dc_cltm` | `100,100,75,80,50,60,30,50,20,40,10,30,1,20` | `1,100` |
| `tvpm_txchain_ppm` | `60,2,1,1` | `1,2` |

These are file declarations. Threshold calibration, the interpretation of zero voltage thresholds, and the mapping of table entries to applied duty cycle, chains, and backoff still need firmware or bench evidence. [Raw declarations](../evidence/2026-11-17-tvpm.json)

## Signed driver and published telemetry

The legacy capability table maps `tvpm` to feature bit 59. During firmware setup the driver calls `configureTVPM`, checks that bit, and supplies an initial period argument of one to `configureTVPMPeriodicity`. The latter checks the cached period and can defer its initial request while waiting for IP setup. The current firmware period remains unmeasured. [Signed path evidence](../evidence/2026-11-17-tvpm.json)

The signed `setTHERMAL_INDEX` and `setPOWER_BUDGET` methods both check the TVPM feature and validate that the index is in the range **1–100** before sending their requests. The latter identifies its value as a PPM index in the driver's diagnostics. Their corresponding getters return two distinct fields from the driver's host cache. The two input indices and the radio temperature measurement have separate sources. [Signed request and getter entry points](../evidence/2026-11-17-tvpm.json)

The driver's `parsePerSliceContainer` path passes firmware telemetry records to `reportTVPM`. The published groups for slice indices 0 and 1 each name eight values. The labels include `Tx Duty Cycle (%)`, `Tx Power Backoff (1/4dBm)`, `Temperature (C)`, and `Battery Voltage (10xV)`, alongside active chains, PPM, CTLM index, and update count. The driver also has a mitigation event path with size, version, and slice checks. Its diagnostic can include the slice, mitigation flags, and event time. [Published labels and entry points](../evidence/2026-11-17-tvpm.json)

A targeted two-hour unified log query found zero matches for the known TVPM configuration, periodicity, and mitigation messages after excluding the query process. The registry inventory read the published names. A request for report values uses a separate update path that can enter firmware commands. [Log and sample scope](../evidence/2026-11-17-tvpm.json), [IOReport update path](cca-provenance.md#ioreport-catalog-and-sample-path)

## Read-only reproduction and bench measurement

```sh
swift tools/read_wifi_status.swift --sample 4 0.5 --thermal --traffic | python3 tools/summarize_link.py
python3 tools/read_macos_inventory.py
/usr/bin/pmset -g therm
```

`--thermal` adds the public host thermal state beside each link snapshot. The summary counts the reported states. The inventory lists the TVPM value labels under `wifi.tvpm_reporting`. In the sample, `pmset -g therm` reported the absence of recorded thermal and performance warnings and CPU power status. [Link sampler](../tools/read_wifi_status.swift), [Link summary](../tools/summarize_link.py), [Host power measurements](host-power-policy.md)

On a second A2337 with console access and an independent receiver, run the same ordinary upload workload on 2.4 GHz and 5 GHz with a fixed AP, channel, and placement for each comparison. Keep the ambient conditions in Apple's specified 10–35 °C operating range. Record the host thermal state, the radio's TVPM values if available, link rate, retries, and throughput around naturally occurring changes. Check which radio field changed before attributing a throughput drop to power backoff, transmit duty, or chain selection. This also provides a way to test whether reducing an app's background transfer rate at elevated host thermal states improves latency. [A2337 operating requirements](https://support.apple.com/en-us/111883), [Apple thermal-state guidance](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/power_efficiency_guidelines_osx/RespondToThermalStateChanges.html)
