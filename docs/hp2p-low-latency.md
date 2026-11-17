# HP2P low-latency and transmit completion paths

The running BCM4378 publishes `hp2p`. In both signed AppleBCMWLAN slices, that feature leads to a second firmware read. Two bits from the reply control a NAN low-latency configuration branch and a PCIe transmit-status branch. The driver paths, the three installed BCM4378 images, and the published state below were checked on macOS 27.2.1 build 26B131. [Driver and firmware evidence](../evidence/2026-11-17-hp2p-low-latency.json), [Capability negotiation](extended-firmware-capabilities.md)

## How the driver uses the HP2P reply

The legacy and extended capability parsers both call `AppleBCMWLANCore::getHP2P_CTRL` after identifying HP2P support. The helper returns a 32-bit word through its output argument. After a successful read the callers test the same two bits and set separate cached bytes. These are positions in the HP2P reply word. The parent capability uses driver feature bit 86. [Per-slice addresses and bit tests](../evidence/2026-11-17-hp2p-low-latency.json)

| HP2P reply bit | Signed-driver consumer | Observed effect in the code |
| --- | --- | --- |
| 2 | `isRllwEnabled` | `setNAN_LLW_PARAMS` checks this flag and selects a different parameter branch for a NAN low-latency request before sending a firmware update scoped to the interface. |
| 3 | `isSplitTxStatusEnabled` | The Skywalk and PCIe transmit enqueue paths use the flag when preparing certain low-latency flow requests. The Skywalk completion drain tests it before interpreting additional transmit-status fields. |

The NAN interface's `getRLLW_STATS` runs the same per-interface firmware read helper used by `getHP2P_CAPS` twice with different selectors. The resulting status fields and their units remain unmeasured. The published `llw0` interface and `wlan.llw.tx.ring.size = 512` establish the host queue configuration. The registry and 602-row IOReport legend sample yielded no named readout of either HP2P flag. [NAN callsites and published state](../evidence/2026-11-17-hp2p-low-latency.json), [Host and PCIe queue sizing](pcie-queue-sizing.md)

## Firmware records across B1 and B3

Honshu and Capri B1 and Kyushu B3 each contain a contiguous group of five 12-byte records. Under the Linux BCM4378 RAM-origin model, the first word of each record points to the named NUL-terminated string below. The other eight bytes of each record match across all three builds. The shape resembles the variable-name record used in published Broadcom source. The shipped firmware's handler behavior, access rules, and parameter units still need separate evidence. [Three-image comparison](../evidence/2026-11-17-hp2p-low-latency.json), [Linux RAM origin](https://github.com/torvalds/linux/blob/v6.12/drivers/net/wireless/broadcom/brcm80211/brcmfmac/chip.c#L744-L745), [Broadcom reference record](https://android.googlesource.com/kernel/common.git/%2B/bcmdhd-3.10/drivers/net/wireless/bcmdhd/include/bcmutils.h)

| Record order | String |
| --- | --- |
| 1 | `hp2p_lfrag_rsrv`, a pointer into the suffix of `bus:hp2p_lfrag_rsrv` |
| 2 | `hp2p_ll` |
| 3 | `hp2p_txop` |
| 4 | `hp2p_host_latency_cnt` |
| 5 | `hp2p_dur` |

The same three images also contain adjacent aligned pointers to `hp2p_txcmpl` and `hp2p_rxcmpl` elsewhere in the payload. The use of these completion labels in an active session remains open. [Firmware names and file offsets](../evidence/2026-11-17-hp2p-low-latency.json)

## Supported app control and a bench comparison

A native Swift probe set and cleared `NWParameters.includePeerToPeer` on a process-local TCP parameters object. It read back `false`, `true`, and `false`. Apple documents that setting for connections and listeners using Apple peer-to-peer Wi-Fi. A separate native type-check rejected `WACapabilities` as unavailable on macOS. The registry snapshot shows an active `awdl0`, a registered `nan0`, and eight zero bytes for `wlan.awdl.params`, matching the value in all 56 installed macOS board plists. [Native probes and role snapshot](../evidence/2026-11-17-hp2p-low-latency.json), [Apple networking API guide](https://developer.apple.com/documentation/technotes/tn3151-choosing-the-right-networking-api#Peer-to-peer-networking)

On a separately managed A2337 and an owned Apple peer, compare a small interactive flow over the documented peer-to-peer API with the same flow on the infrastructure network. Record median and 95th-percentile round-trip time, transfer rate, and `awdl0` and `en0` byte deltas during simultaneous infrastructure traffic. A separate receiver observing the owned links can establish whether their airtime overlaps or alternates. Prior AWDL measurements show how availability windows can time-share a radio with an access point. A driver-owned record of the HP2P reply and completion events would be needed to connect the observed latency to RLLW or split transmit status. [Role counter sampler](../tools/read_link_role_counters.py), [Original AWDL timing study](https://arxiv.org/abs/1808.03156)

## Reproduce the offline image comparison

```sh
firmware_root=/System/Library/DriverExtensions/com.apple.DriverKit-AppleBCMWLAN.dext/Firmware
python3 tools/inspect_hp2p_firmware.py \
  "$firmware_root/C-4378__s-B1/honshu.trx" \
  "$firmware_root/C-4378__s-B1/capri.trx" \
  "$firmware_root/C-4378__s-B3/kyushu.trx"
```

The tool checks the five pointers together and hashes the non-pointer bytes for cross-build comparison. For the process-local API check, import `Network`, create `NWParameters.tcp`, and read `includePeerToPeer` before and after setting it to `true` and then `false`. [Offline image tool](../tools/inspect_hp2p_firmware.py)
