# Retry limits and frame aggregation on the BCM4378

An A-MSDU carries several service data units inside one MAC protocol data unit (MPDU). An A-MPDU combines MPDUs in one PHY transmission. Block Ack reports reception across sequence numbers in an agreement for a traffic identifier (TID). The Retry bit indicates a retransmission as marked by the sender. [Wireshark 802.11 fields](https://www.wireshark.org/docs/dfref/w/wlan.html), [Radiotap A-MPDU status](https://radiotap.org/fields/A-MPDU%20status.html)

## macOS driver behavior

The running Shikoku firmware publishes `ampdu`, `ampdu_tx`, `ampdu_rx`, `amsdurx` and `amsdutx`. The public IOReport legend on macOS 27.2.1 has 27 chip-level A-MPDU labels, including transmitted and received Block Ack, delimiter errors, and out-of-window receives. It also has separate ranges of 64 bucket labels for transmit, single-user receive, and OFDMA receive aggregate statistics. The repository inventory reads these names and indexes under `wifi.aggregation_counter_legend`. The numbers identify the published buckets. Their current values and the chip's applicable aggregation limits remain unmeasured. [Live capability and catalog readback](../evidence/2026-11-17-retries-and-aggregation.json)

| Path in both signed driver slices | Verified behavior |
| --- | --- |
| Default mode and WME setup | Request long retry limit 6, and short retry limit 7 when that branch is enabled. |
| Associated real-time mode branch | Requests long retry limit 12. |
| Link-change event | Calls the Block Ack window configuration path when feature bit 89 is set. The legacy firmware capability mapped to it is `adv_ecounters`, present in the current `FWCap` response. |
| Block Ack window configuration | Uses separate transmit and receive requests. A driver state byte selects receive constants 16 or 64 and transmit halfwords whose low bytes are 16 or 64. The transmit halfwords also carry a high byte. |
| Net adapter's limited-aggregation method | Returns zero immediately. |

The retry limits in the table are arguments of private firmware requests. The configured values, which branch ran on this association, and how the peer negotiated its Block Ack window require bench measurements. The supported per-socket service types documented elsewhere set host traffic classes. [Driver branch evidence](../evidence/2026-11-17-retries-and-aggregation.json), [Legacy feature-bit mapping](firmware-capabilities.md), [Socket class controls](wifi-traffic-scheduling.md)

The DriverKit numeric transmit-rate path checks association and divides a cached rate value by 1,000 with integer arithmetic. Its separate private HE MCS getter requests `nrate` and checks the encoding field in the reply. The public CoreWLAN transmit-rate getter is usable with the repository sampler. Use packet metadata to measure the rate selection and retransmission sequence on a test link. [Signed rate-reader trace](../evidence/2026-11-17-retries-and-aggregation.json), [CoreWLAN transmit rate](https://developer.apple.com/documentation/corewlan/cwinterface/transmitrate%28%29)

## Linux and Asahi retry controls

Both pinned brcmfmac trees implement `set_wiphy_params` and require the interface to be up. A request can set the short and long retry attributes through `iw`. The driver visits the long retry branch first when both values change and returns as soon as a write succeeds. Netlink stores both requested values before calling that handler, and the `iw phy info` readback reports those stored values. The operation tables omit the standard bitrate-mask callback. [Stable brcmfmac handler](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L1626-L1685), [Asahi handler](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c#L1272-L1333), [Netlink write and rollback](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/net/wireless/nl80211.c#L4552-L4593), [Bitrate-mask trace](asahi-controls.md#standard-controls-and-readouts)

Compiling the exact driver functions against a mock firmware sender produced one write in each tree for a combined request. With initial limits 7 short and 4 long, a request for 8 and 5 returned success and changed only the simulated long limit to 5. A separate short-limit request then wrote 8. When a mock short-limit write failed, the driver's private configuration still cached the request. Retrying that same value returned success on the second call without a second firmware write. These results verify the source behavior in the harness. [Compiled harness results and source hashes](../evidence/2026-11-17-retries-and-aggregation.json)

On a separate A2337 running Asahi, record `iw phy "$PHY" info` and station statistics before testing. Use distinct `iw phy "$PHY" set retry short "$SHORT_LIMIT"` and `iw phy "$PHY" set retry long "$LONG_LIMIT"` requests. Check the test link after each request with the same traffic direction and workload. The AP or an independent recorder can measure retries and stalls after a change. [iw command definition](https://kernel.googlesource.com/pub/scm/linux/kernel/git/jberg/iw/%2B/c5bfa2a3a9720ae3af84d20ad561c8a46e6173a1/phy.c)

## Measuring aggregation from a saved capture

```sh
python3 tools/summarize_he_capture.py --aggregation /path/to/bench-capture.pcapng
```

The tool groups runs of equal Radiotap A-MPDU references per capture section, interface, and reported channel frequency. A known last-subframe marker closes the run. It counts records with a decoded MAC frame subtype and excludes zero-length records indicated by a recorder that reports them. It reports runs with and without a last marker. Even a marked run can start after the first subframe or miss a record. A run size of zero means the run yielded no qualifying frame subtypes. Missing channel metadata leaves channel collisions unresolved. The tool also counts the Retry and A-MSDU flags on data-type records and the Block Ack Request and Block Ack subtypes. [Capture tool](../tools/summarize_he_capture.py), [Radiotap reference and flags](https://radiotap.org/fields/A-MPDU%20status.html)

In the public Wi-BFI HE80 trace, 8,141 of 272,634 capture records carried a Radiotap A-MPDU reference. Its longest observed run contained 20 records with decoded frame subtypes. Every run lacked a known last marker. The trace also contained 192 data-type records with the Retry bit, 2,362 with A-MSDU present, 13 Block Ack Requests, and 75,626 Block Ack frames. The multisection synthetic fixture checked a reference of zero, repeated references, zero-length records, and the known flag. [Public Wi-BFI trace](https://github.com/kfoysalhaque/Wi-BFI/blob/47ca7f842d6efdff2f83b981a7c119327e8dc2d6/traces/11ax_SU_4x2_80.pcapng), [Capture verification](../evidence/2026-11-17-retries-and-aggregation.json)

For an owned AP and separate A2337, record the transmitted and received directions under the same traffic load. Use Add Block Ack request and response frames or AP diagnostics to identify the buffer size and accepted TID, then compare the decoded aggregates and the data retry flags for that direction. Repeat the measurement under controlled attenuation to distinguish retry behavior from a change in PHY rate.
