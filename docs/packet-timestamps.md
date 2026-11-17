# Packet timestamps and PCIe time measurement on the BCM4378

The signed driver also negotiates chip-delay count scales for PCIe completion records. The scale arithmetic and the host milliseconds used by the `TxCompletion Latency` histogram have their own trace. [Chip-delay and completion latency](chip-delay.md)

The running Shikoku core on macOS 27.2.1 publishes `PTM_Mode = 1`. The `SIOCGIFCAP` query on `en0` returned `0x6460` for both the supported and enabled masks. The hardware and interface software timestamp flags are clear in both masks. An IPv4 loopback UDP socket received wall-clock and monotonic timestamps with the corresponding socket options enabled. XNU constructs those messages in the receive path using `getmicrotime` and `mach_absolute_time`. [Live readouts](../evidence/2026-11-17-packet-timestamps.json), [XNU interface getter](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/net/if.c#L3907-L3912), [XNU IPv4 timestamp creation](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/netinet/ip_input.c#L3387-L3411)

## Clock paths in the signed driver

The legacy driver capability table maps `tsync` to bit 52 and `ptm` to bit 91. Both words are absent from the live legacy reply. Both signed driver slices also have paths in the extended feature parser that can set those bits. The driver's legacy timestamp capability check tests bit 52. All three distinct installed BCM4378 images contain `rte_timesync` and `time_sync_opt`. The driver's timekeeper reads `mach_continuous_time` and can send a clock sync request using `rte_timesync`. Actual device clock updates remain unmeasured. [Firmware and native trace](../evidence/2026-11-17-packet-timestamps.json), [Legacy capability parser](firmware-capabilities.md)

`setPTMMode` initializes its core mode to 1, checks feature bit 91 and consults `ptm_active` on eligible paths. The property publisher copies the core mode to `PTM_Mode`. Normal setup passes a Boolean to the PCIe interface that is false for core mode 1. The bus chooses its timestamping state from that Boolean and a separate policy input. Its diagnostic table labels bus modes 1, 2, and 3 as PTM, legacy hardware, and software timestamping. This decode follows both vtable calls into the PCIe implementation and resolves the diagnostic strings through the Mach-O fixups. [Dual-slice dispatch and mode evidence](../evidence/2026-11-17-packet-timestamps.json)

The PCIe transmit and receive timestamp paths check message and clock information before mapping a PTM timestamp into the host absolute time domain. The private infrastructure `getTIMESYNC_INFO` dispatches to a capability formatter. The separate `getFW_CLOCK_INFO`, `getTIMESYNC_STATS`, and `setTIMESTAMPING_EN` methods return `kIOReturnUnsupported` in this build. The published property and interface flags establish the current host exposure. Actual firmware timestamp messages and the radio clock state remain open. [Timing functions and results](../evidence/2026-11-17-packet-timestamps.json)

## Readouts on macOS and Linux

```sh
timestamp_probe_dir=$(mktemp -d -t bcm4378-timestamp-probe)
cc -std=c17 -D_DARWIN_C_SOURCE -Wall -Wextra -Werror \
  tools/probe_macos_timestamps.c -o "$timestamp_probe_dir/probe_macos_timestamps"
"$timestamp_probe_dir/probe_macos_timestamps" en0
python3 tools/read_macos_inventory.py
```

The probe reads the two interface masks and sends a one-byte datagram to its own IPv4 loopback address. The inventory records the core property as `wifi.pcie_ptm_mode`. For an app measuring local delivery, use `mach_absolute_time` after `recvmsg` and convert the difference from `SCM_TIMESTAMP_MONOTONIC` with the host timebase. This measures elapsed time after the kernel constructed the ancillary data. An echo measurement can give round-trip delay to an owned LAN peer using the local clock. [Public probe](../tools/probe_macos_timestamps.c), [Core property inventory](../tools/read_macos_inventory.py), [XNU socket behavior](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/netinet/ip_input.c#L3387-L3411)

The pinned stable Linux and Asahi brcmfmac ethtool tables register a driver-info handler. Their netdev operations lack hardware timestamp handlers. On a separate Linux test device, `ethtool -T "$IFACE"` can show the kernel timestamp capabilities. Linux can advertise generic receive software timestamping through its fallback. The brcmfmac monitor receive path passes firmware-provided Radiotap through as supplied. The alternate hardware receive header contains partial TSF fields. In this path the driver strips the header and inserts an empty Radiotap header. The selected macOS firmware's ID is outside the two hardware-header exceptions in the pinned Linux table. Monitor format and timestamps on a booted Asahi A2337 remain unverified. [Stable monitor path](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/core.c#L434-L471), [Asahi monitor path](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/core.c#L434-L471), [Linux capability paths](../evidence/2026-11-17-packet-timestamps.json)

## Timing fields in a saved capture

Radiotap TSFT is the receiving MAC's 64-bit microsecond timer at the first bit of an MPDU. The optional Radiotap timestamp has its own counter width, units, accuracy flag, and sampling position. The beacon timestamp belongs to the transmitting BSS. A capture record timestamp has the recorder's own clock provenance. [Radiotap TSFT definition](https://radiotap.org/fields/TSFT.html), [Radiotap timestamp definition](https://radiotap.org/fields/timestamp.html), [Wireshark WLAN fields](https://www.wireshark.org/docs/dfref/w/wlan.html)

```sh
tshark -n -o wlan.enable_decryption:FALSE -r /path/to/saved-capture.pcapng \
  -T fields -E occurrence=f -e frame.number -e frame.time_epoch \
  -e wlan.fc.type_subtype -e wlan.fixed.timestamp \
  -e radiotap.mactime -e radiotap.timestamp.ts -e radiotap.timestamp.unit \
  -e radiotap.timestamp.samplingpos -e radiotap.timestamp.flags.32bit \
  -e radiotap.timestamp.flags.accuracy -e radiotap.timestamp.accuracy
```

In the public Wi-BFI HE80 sample, all 272,634 records carried the optional timestamp. The recorder described it as a 32-bit microsecond counter at PLCP acquisition and reported 22 µs accuracy. There were 263,926 records with both receive-side fields and 546 beacons with both receive-side fields plus the transmitter timestamp. Modulo the 32-bit wrap, subtracting the optional timestamp from TSFT gave −72,996 to −72,993 µs. The nearly constant difference is consistent with an offset between the reported clocks. A one-way delay measurement would require clock alignment, known sampling points and independent calibration. [Pinned Wi-BFI capture](https://github.com/kfoysalhaque/Wi-BFI/blob/47ca7f842d6efdff2f83b981a7c119327e8dc2d6/traces/11ax_SU_4x2_80.pcapng), [Timestamp sample summary](../evidence/2026-11-17-packet-timestamps.json)

For an A2337 bench test, use an owned AP and independent receiver on a fixed channel. Record packet times on the same observer clock when comparing over-the-air intervals. Pair that record with an application echo test to measure delivery jitter. Across AP or peer sessions, allow for Apple's documented randomized starting TSF offset. [Apple TSF randomization](https://support.apple.com/en-ca/guide/security/sec31e483abf/web)
