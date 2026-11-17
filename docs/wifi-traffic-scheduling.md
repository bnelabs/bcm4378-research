# BCM4378 traffic scheduling and application controls

On the M1 MacBook Air, an application can request a network service type or a TCP pacing ceiling on its own socket. The host scheduler exposes queue groups and delay targets. The Wi-Fi driver publishes per-traffic-ID frame counter names. [Socket, queue, and firmware evidence](../evidence/2026-11-17-wifi-traffic-scheduling.json)

## Socket controls verified on macOS 27.2.1

All nine SDK `NET_SERVICE_TYPE_*` values passed `SO_NET_SERVICE_TYPE` set and readback on unbound, unconnected IPv4 and IPv6 TCP and UDP sockets. Each fresh socket started at best effort. The six documented `NWParameters.ServiceClass` cases type-checked with the macOS 27.2 SDK. [BSD probe](../tools/probe_socket_qos.c), [Apple Network framework service classes](https://developer.apple.com/documentation/network/nwparameters/serviceclass-swift.enum)

Published XNU maps the BSD service type to socket traffic metadata and sets a service class on outgoing packets. The driver-managed FQ-CoDel path groups those classes as shown below. The active `en0` scheduler reports these four groups. XNU has additional classification rules for system traffic and some TCP ACKs and SYNs. [Socket class table](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/netinet/in_tclass.c#L134-L144), [Service type setter](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/netinet/in_tclass.c#L970-L990), [Packet metadata](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/netinet/in_tclass.c#L1193-L1265), [FQ-CoDel grouping](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/net/pktsched/pktsched_fq_codel.c#L665-L695)

| Requested BSD service types | Driver-managed host queue group |
| --- | --- |
| Best effort (BE), responsive data (RD), operations and management (OAM) | BE |
| Background (BK) | BK |
| Signaling (SIG), interactive video (VI), responsive media (RV), streaming media (AV) | VI |
| Interactive voice (VO) | VO |

`SO_MAX_PACING_RATE` accepted 125,000 bytes/s on all four socket combinations. The initial read was `UINT64_MAX`. The pinned XNU TCP transmit path uses a finite rate to enter its packet pacing calculation. The option also read back on UDP sockets. Actual send timing and throughput remain unmeasured for both transports. [XNU pacing option](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/kern/uipc_socket.c#L5684-L5703), [TCP output pacing](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/netinet/tcp_output.c#L2485-L2514), [Probe results](../evidence/2026-11-17-wifi-traffic-scheduling.json)

On a connected test flow, `SO_NETSVC_MARKING_LEVEL` can read the socket's marking policy for its last outgoing interface. Managed Wi-Fi profiles can apply an app allowlist through `QoSMarkingPolicy`. IP DSCP and 802.11 user priority are distinct fields. The AP's mapping affects the downstream result. [XNU marking getter](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/netinet/in_tclass.c#L872-L911), [Apple Wi-Fi marking policy](https://developer.apple.com/documentation/devicemanagement/wifi/qosmarkingpolicy-data.dictionary), [RFC 8325](https://www.rfc-editor.org/rfc/rfc8325.html)

## Live scheduler and firmware reporting

| Interface | Kernel send queue groups from `netstat -q` | Dequeued packets in the sample |
| --- | --- | --- |
| `en0` | VO, VI, BE, BK | Nonzero in all four groups |
| `awdl0` | VO, VI, BE, BK | Nonzero in VO, BE, and BK |
| `llw0` | CTL, VO, VI, RV, AV, OAM, RD, BE, BK, BK_SYS | Zero |
| `ap1` and `nan0` | VO, VI, BE, BK | Zero |

Each scheduler reported a 6,720-packet limit, a **10 ms** classic queue-delay target, a **100 ms** classic update interval, and a **15 ms** L4S queue-delay target. Published XNU selects 15 ms as its wireless L4S default and exports both targets from the host queue group. L4S packet and CE mark counters read zero. End-to-end L4S needs ECN feedback and a supporting bottleneck. [Queue readouts](../evidence/2026-11-17-wifi-traffic-scheduling.json), [XNU queue delay selection](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/net/pktsched/pktsched_fq_codel.c#L488-L531), [XNU queue stats](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/net/pktsched/pktsched_fq_codel.c#L2687-L2701), [RFC 9330](https://www.rfc-editor.org/rfc/rfc9330.html#section-2)

The signed driver's `getTxSubQueue` selects a Skywalk submission queue using a WME access-category index. The PCIe flow path passes an access category through `requestFlowId` before `createFlow`. The live `FWCap` string includes `wme`. The report legend names transmit and receive MPDU counters for traffic IDs 0–7 on each of two published slices. It also lists per-TID receive-loss counters for Block Ack and non-Block Ack traffic. Firmware event record parsers feed the per-slice report writers. The inventory key `wifi.wme_tid_reporting` reads the published label catalog. Actual counter deltas and the TIDs used by individual flows remain unmeasured. [Driver and legend evidence](../evidence/2026-11-17-wifi-traffic-scheduling.json), [PCIe queue sizing](pcie-queue-sizing.md)

Stable Linux 7.3.4 and Asahi 7.3.4-2 contain identical `flowring.c` files. The unicast priority map assigns priorities 0–7 to flow-ring FIFOs `0, 1, 1, 0, 2, 2, 3, 3`. The ring-creation message uses that FIFO in its TID field and the transmit descriptor retains the original three-bit packet priority. [Linux FIFO mapping](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/flowring.c#L28-L37), [FIFO getter](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/flowring.c#L168-L175), [Linux ring creation](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.c#L644-L650), [Linux transmit priority](https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.c#L764-L774), [Asahi FIFO mapping](https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/flowring.c#L28-L37)

## Additional firmware policy paths

- **Mirrored Stream Classification Service (MSCS).** A station can negotiate with its AP to mirror upstream traffic classification onto downstream traffic. The signed driver's `sendQoSMgmtMSCSReq` checks driver feature bit 95, a local policy flag, and current AP support. The legacy parser sets that feature bit from the exact `qos_mgmt` word. That word is absent from Shikoku's published reply. The extended reply and an MSCS exchange on this BCM4378 remain unverified. [Wireless Broadband Alliance QoS overview](https://wballiance.com/wp-content/uploads/2023/04/Private-5G-and-Wi-Fi-Convergence-Use-Cases_PUBLIC-April.pdf#page=19), [Firmware capability provenance](firmware-capabilities.md), [Driver trace](../evidence/2026-11-17-wifi-traffic-scheduling.json)
- **Aggressive EDCA.** EDCA controls how access categories contend for the medium. Both driver slices contain an eligibility path requiring driver country code `CN` and a numeric chip ID above 4387 or chip 4387 at revision C3. The BCM4378 B1 falls below that chip gate. The driver has a link-quality decision and a station WME parameter write path. Its `changeAggregationPerEDCATID` routine provides a separate private path for adjusting aggregation for TIDs 0–7 and for Block Ack setup or teardown. Use of that routine on this connection remains unmeasured. [Driver trace](../evidence/2026-11-17-wifi-traffic-scheduling.json), [BCM4378 B1 identity](firmware-layout.md)

## Reproduction and bench tests

```sh
bcm4378_qos_dir=$(mktemp -d)
xcrun clang -std=c11 -D_DARWIN_C_SOURCE -Wall -Wextra -Werror \
  -o "$bcm4378_qos_dir/probe_socket_qos" tools/probe_socket_qos.c
"$bcm4378_qos_dir/probe_socket_qos"
/usr/sbin/netstat -q -I en0
/usr/sbin/netstat -q -I llw0
python3 tools/read_macos_inventory.py
```

The socket probe sets options on its own unconnected descriptors and closes them. The other commands read the host scheduler and registry. The evidence lists both signed driver slices and the method addresses for a static reproduction. [Evidence](../evidence/2026-11-17-wifi-traffic-scheduling.json)

1. **Protect interactive traffic during bulk transfers.** On a second A2337 with console access, a separate AP, and a wired peer, run a voice-like flow alongside a file transfer. Compare default settings with a voice service class and a background bulk class. Correlate host queue deltas, AP-observed TIDs, throughput, and 95th-percentile delay.
2. **Measure burst reduction.** Set a finite pacing rate on the test TCP transfer and compare peer arrival bursts and queue delay with the default over equal intervals. Observe each direction before attributing a change to the radio.
3. **Verify the newer QoS paths.** For MSCS, look for advertised peer support, a completed setup exchange, and downstream TID changes. For L4S, measure a QUIC test flow across a controlled bottleneck that supports L4S. Observe ECT(1), CE feedback, and delay alongside the host readout. [Apple L4S test procedure](https://developer.apple.com/documentation/network/testing-and-debugging-l4s-in-your-app)
