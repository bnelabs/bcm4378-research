# Know Your Wifi

KYW is a native SwiftUI macOS app for exploring the Broadcom BCM4378 research. It targets macOS 14 or later. The tested build used Xcode 27.2 on macOS 27.2.1. The bundled country, timing and firmware decoders need Python 3.9 or later. The release bundle is ad hoc signed for local use.

```sh
./app/build.sh
open "app/dist/Know Your Wifi.app"
```

| Where to go | What you can do |
| --- | --- |
| **Overview** | Read signal, noise, negotiated speed and how busy the channel is. Pin a signal reading before moving to another spot. Save a timestamped link snapshot. |
| **Spectrum** | See the channels macOS offers in the current country. Compare two stored country plans before configuring an access point you manage. |
| **Experiments** | Measure channel visits and switch delays. Run a local workload with short updates and a bulk archive, then test whether updates stay on time while the archive connection breaks and resumes. Use a shared key to compare ordinary Wi-Fi with one stream on a direct link between two Macs you manage. |
| **Geek’s Corner** | Read the chip, board, PCI ID, firmware ID and selected image hash. See the RTOS evidence, search the upstream ThreadX CVE snapshot and inspect installed or saved files. |
| **Research** | Search the detailed notes and the saved evidence behind them. |

## What you can change in Geek’s Corner

| Setting | Effect |
| --- | --- |
| **Traffic priority** | Pick from the nine macOS classes, including video, voice, streaming and background. KYW explains each class and sets and verifies it on its own test socket. |
| **Pacing** | Ask macOS for a sending cap in bytes per second. A lower cap can give other traffic more room and extend a transfer. KYW reads the value back on the test socket. |
| **Radio power** | Turning the radio off stops Wi-Fi, including direct wireless links. Turning it on can let macOS rejoin a saved network. |
| **Detached channel** | Ask macOS to tune an idle radio to a currently supported channel. Joining an access point lets macOS select its channel. |

Radio power and channel changes require detached Wi-Fi and an independently verified Ethernet default route. KYW checks those conditions again just before applying a radio command. Country profiles are for planning. Apple’s driver and Broadcom’s firmware manage the active country, power limits and antenna policy.

## How to read the firmware and security evidence

The driver supplies the active firmware version and the path it requests. On the measured M1 MacBook Air, the requested Shikoku image resolves to Honshu. Its SHA-256 matches a saved disassembly finding in which initialization prints **ThreadX 5.6**. KYW labels unmatched images as unidentified. It can decode the local firmware, two wireless-core programs, board settings, and retained distance, wake, keepalive and ThreadX memory records. [RTOS evidence](../docs/rtos-threadx.md), [Firmware layout](../docs/firmware-layout.md)

Geek’s Corner shows the 24 CVEs in the Eclipse ThreadX repository as checked on 17 November 2026. Each entry includes its reported effect, upstream version range and fix. Broadcom’s build may use a different patch set and optional components, so its exposure is unknown. Live access to firmware registers or RAM and an interactive ThreadX console remain unverified. [Eclipse ThreadX advisories](https://github.com/eclipse-threadx/threadx/security/advisories)

## Verify the local build

```sh
"app/dist/Know Your Wifi.app/Contents/MacOS/KYW" --self-test
```

The check reads the live driver and stock files, verifies the radio-control guards and a TCP socket’s settings, and runs archive recovery using generated data on the local interface. The two-Mac transfer and the physical effects of detached radio settings require separate hardware.
