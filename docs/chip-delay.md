# BCM4378 chip-delay fields and host completion latency

The signed AppleBCMWLAN driver has a PCIe negotiation path for converting TX and RX chip-delay counts to microseconds. The conditional defaults are **128 µs per TX count and 32 µs per RX count**. The published `TxCompletion Latency` histogram follows a separate path. DriverKit records the elapsed time from a saved packet timestamp to host completion in whole milliseconds. The negotiated scales and live chip-delay samples remain unverified on this Mac. [Signed driver, cache, and registry evidence](../evidence/2026-11-17-chip-delay.json)

## Scale selection at PCIe startup

In both signed slices, `createFirmwarePCIeIPC` reads the second firmware shared flag word. Bit 20 selects a branch that initializes the TX and RX exponents to 2 and 0. Internal numeric overrides can replace those defaults. The driver caps each exponent at 7, packs both three-bit values into the host capability word it returns to firmware, and saves `32 << exponent` as each direction's microseconds-per-count multiplier. A separate firmware flag and the host low-latency policy gate the TX timestamp path. The core's published `PTM_Mode` describes a separate clock mode. [Startup and multiplier trace](../evidence/2026-11-17-chip-delay.json), [PTM and ordinary packet timestamp paths](packet-timestamps.md)

| Direction | Count width | Default step | Largest representable offset at the default |
| --- | ---: | ---: | ---: |
| Transmit | 10 bits per field | 128 µs | 130,944 µs |
| Receive | 16 bits | 32 µs | 2,097,120 µs |

The startup argument names for the two scale overrides were absent. All 56 stock macOS board profiles also omit those keys. The table gives the range for the conditional default path. The current firmware shared flags and the resulting live scales remain open. [Stock configuration and static range calculation](../evidence/2026-11-17-chip-delay.json)

## Transmit and receive completion arithmetic

In the timestamp-enabled send path, both PCIe flow queue implementations convert `mach_continuous_time` to whole microseconds and store its low 32 bits in a submission record. The TX completion drain separately combines three packed counts with an existing nanosecond timestamp in the packet's private scratch area. The exact event that supplies this saved timestamp and the hardware meaning of each count need further evidence. [Submission and completion trace](../evidence/2026-11-17-chip-delay.json)

For counts `a`, `b`, and `c` in field order and TX step `s` in microseconds, the TX branch writes three results.

- The first timestamp is `base_ns + 1000 × a × s`.
- The middle interval is `max(0, b − a) × s` in microseconds.
- The third timestamp is `base_ns + 1000 × max(b, c) × s`.

The first timestamp is written before the code clamps the first count for the middle interval. The integer replay includes a case with out-of-order counts to preserve that distinction. Nanosecond storage for two results retains the time scale of the packet's base timestamp. The firmware counts contribute changes in steps of `s` microseconds. [Arithmetic replay](../evidence/2026-11-17-chip-delay.json)

The RX helper records a separate host continuous-time value in whole microseconds. It chooses a base from the completion record and converts the extended clock field to microseconds when the item format and clock tag match. It multiplies the unsigned 16-bit delay count by the RX step and adds it to the base. The result is stored modulo 2³² microseconds, which wraps about every 71.6 minutes. [Receive instructions and wrap check](../evidence/2026-11-17-chip-delay.json)

## What the Mac actually reports

The public-marked IOReport legend contains `TxCompletion Latency` for `en0` and per-peer groups. In the installed IO80211DriverKit cache, `skywalkLogTxCompletionPacket` converts the current host time to nanoseconds and subtracts the saved packet timestamp. It passes the same elapsed value into the peer and interface histogram paths. Both paths convert it to whole milliseconds and tally it in a traffic-class histogram. The legend registration in both paths points to the same `TxCompletion Latency` string. The WLAN registry read captured the channel descriptions. Live bucket values remain unmeasured. [DriverKit histogram trace and live legend](../evidence/2026-11-17-chip-delay.json)

The stock `en0` query again reports both hardware timestamp bits clear, while a UDP loopback received kernel wall and monotonic timestamps. The loopback result establishes the socket clock path. The corresponding handlers in the two pinned Linux trees use packet IDs and ring state for TX bookkeeping and RX lengths and flags for receive delivery. Those handlers leave the chip-delay fields unread. [Native timestamp probe](../tools/probe_macos_timestamps.c), [Pinned stable Linux completions](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.c#L900-L931), [Pinned Asahi receive completion](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.c#L1215-L1255)

On a separately managed A2337, pair a controlled same-channel traffic run with an independent receiver and an application timestamp. Compare the receiver's airtime intervals, app round-trip times, and any retained driver completion records as separate measurements. If the driver records include the negotiated exponent and both timestamp domains, compare like-for-like packets and account for the count steps and 32-bit RX wrap. The test can quantify changes in host completion time during congestion and establish where finer timing requires an independent receiver. [Existing timestamp methods](packet-timestamps.md), [Peer-link bench comparison](hp2p-low-latency.md)
