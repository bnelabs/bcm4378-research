# Practical applications for the BCM4378

## See a defect while the full image is still in transit

A camera aimed at a conveyor or inspection station can send a small preview as soon as a part passes. An operator or a model on the Mac can classify that preview while the full-resolution image moves into a background archive. Each preview has a deadline tied to the part's position. The sender can discard a preview that will arrive too late to inform a decision and keep its full-resolution evidence. This lets the capture rate follow the physical process even when the uplink slows down.

The prototype models each of 40 frames as a 2 KiB preview and a 40 KiB archive payload. It uses 4 KiB chunks, so a full-resolution transfer makes room for the next preview at the next chunk boundary. Both runs replay the same link at 125,000 bytes/s with a 1.2-second dip to 48,000 bytes/s. With a 160 ms preview deadline, the replay produced these results. [Replay evidence](../evidence/2026-11-17-inspection-stream-replay.json)

| Application policy | Previews on time | 95th-percentile preview delay | Full archive delivered | Archive finished |
| --- | ---: | ---: | ---: | ---: |
| Send requests in arrival order | 1 of 40 | 6,085.956 ms | 1,638,400 bytes | 14.502 s |
| Send time-sensitive previews first | 40 of 40 | 93.007 ms | 1,638,400 bytes | 14.502 s |

The timing uses the modeled bottleneck. The optional TCP loopback run delivered and checked the payload bytes on real connected sockets. macOS read back interactive-video priority for previews and background priority plus a 125,000 bytes/s ceiling for the archive. The link replay exercises scheduling and expiration. Radio delay, achieved over-the-air pacing, and image recognition accuracy require a camera and controlled link. [Native socket and queue trace](wifi-traffic-scheduling.md), [Prototype source](../tools/replay_inspection_stream.py)

```sh
python3 -B tools/replay_inspection_stream.py --loopback
```

With an owned camera, a paired Apple device can send small previews to the Mac over a direct link and transfer full images over the site's access point. Each preview can carry a part ID and an acknowledgement deadline. Compare how many previews arrive in time to inform the inspection decision and how many full images make it to the archive. The A2337 lab result and firmware's dual-band flag support testing this combination. [Peer roles](driver-interfaces.md#running-wi-fi-interfaces), [Dual-band gates](simultaneous-dual-band.md)

The receiver's deadline misses can drive the sender to lower archive pacing or use smaller previews. The published same-network, other-network, and interference readings can help explain the circumstances after the fact. In one 22-second run the connected Mac returned 18% average and 7% other-network CCA at every read. Decisions about immediate rate need the receiver's delivery times because the CCA values can persist across snapshots. [Live airtime values](live-wifi-airtime.md)

Two small HTTPS transfers on this Mac showed that the inspection socket setting can be visible at only part of the path. The video class advanced the tunnel queue while the Wi-Fi video queue and radio's video counters stayed flat. Keep the preview deadline in the sender and receiver, and check physical queue behavior wherever the inspection system is deployed. [Measured tunnel and Wi-Fi queues](wifi-traffic-scheduling.md#where-interactive-priority-showed-up-on-the-connected-mac)

For a portable inspection kit, use the stock country tables to choose a shared 80 MHz block and narrower fallbacks for the camera and Mac. For example, the installed Türkiye, US and Japan rows all contain the block centered at 5,210 MHz. The 80 MHz block containing channel 144 appears in the US and Japan rows and is absent under Türkiye's rules for this Mac. Confirm the owned access point's available settings and the Mac's active list at the site. Record the negotiated width with the preview deadline results so changes to the radio plan can inform the sender's pacing. [Field deployment example and decoder](clm-channel-tables.md#plan-an-access-point-before-a-field-deployment)

### Test the direct link while the archive is moving

The native test opens two authenticated TCP connections. It sends twenty 2 KiB previews at 100 ms intervals and a 1 MiB archive in 4 KiB chunks. The receiver checks each payload against the expected bytes and acknowledges each preview and the complete archive. The sender requests interactive-video service for the previews and background service for the archive. It measures the time from each scheduled release to the receiver's acknowledgement using one monotonic clock. [Probe source](../tools/probe_inspection_peer.swift), [Network framework service classes](https://developer.apple.com/documentation/network/nwparameters/serviceclass-swift.enum)

The sender selects the receiver's Bonjour advertisement on the required interface and stops discovery before opening the connections. It sets `NWParameters.requiredInterface` on each connection. The `split` test requires `awdl0` for previews and the named LAN interface for the archive. The `lan` test uses the named LAN interface for both streams. The connection's transfer report associates application bytes with the interface that carried them. A transfer counts as a successful split only when the report shows payload on both requested interfaces. [Apple peer setup](https://developer.apple.com/documentation/technotes/tn3213-moving-from-multipeer-connectivity-to-network-framework), [Required interface](https://developer.apple.com/documentation/network/nwparameters/requiredinterface), [Per-path transfer report](https://developer.apple.com/documentation/network/nwconnection/datatransferreport/pathreport)

On macOS build 26B131, three local runs discovered the paired receiver through Bonjour on `lo0`. The connections used TLS with a fresh 32-byte shared key. The listener rejected the mismatched key in each run. All 60 preview acknowledgements met the 160 ms deadline, the receiver verified all 3 MiB of archive payload, and the reports attributed both connections in each run to `lo0`. The IPv4 default interface was `en0` and the association was on primary 40 at 80 MHz before and after the runs. [Loopback results](../evidence/2026-11-17-inspection-peer.json)

```sh
inspection_dir=$(mktemp -d -t bcm4378-inspection)
xcrun swiftc -swift-version 6 -warnings-as-errors -O \
  tools/probe_inspection_peer.swift -o "$inspection_dir/probe_inspection_peer"
"$inspection_dir/probe_inspection_peer" selftest
```

For the radio comparison, build the same command on two owned Macs and run it on the independently managed test setup. Generate a fresh key on one test machine and share just that file over a trusted channel with the other one. The listener advertises the test service and runs for 90 seconds.

```sh
(umask 077 && /usr/bin/openssl rand -out "$inspection_dir/pairing.key" 32)
"$inspection_dir/probe_inspection_peer" serve "$inspection_dir/pairing.key"
```

On the sender, use the copied key and its existing LAN interface. Capture JSON from both runs while the receiver is listening.

```sh
"$inspection_dir/probe_inspection_peer" run "$inspection_dir/pairing.key" lan en0
"$inspection_dir/probe_inspection_peer" run "$inspection_dir/pairing.key" split en0
```

Compare preview deadline hits, tail latency and verified archive throughput under the same access-point conditions. The factory map puts the 5 GHz router and a 2.4 GHz direct leg on different Wi-Fi cores if macOS uses those bands. Set the owned test router to 5 GHz and record the peer's band while the split test sends both streams. The path report answers which interface carried the traffic. An independent receiver on each band with a common clock answers which channels carried it and whether transmissions overlapped. The two-device result remains open. [Factory band map and log fields](simultaneous-dual-band.md#factory-band-assignment)

For an inspection cart moving between two owned access points, the application could keep sending time-sensitive previews straight to the nearby operator during a router handoff. The recovery probe measures whether previews arrive while the archive connection reopens. On a separate bench, compare missed previews during handoff with the LAN-only run, then count complete archives by part ID. [Roaming test](wifi-roaming.md), [Archive recovery probe](#resume-work-after-a-radio-fault)

## Wake the Mac when inspection work actually arrives

An owned sensor can hold a small work queue while the Mac sleeps, discover the service over the local network, and submit an analysis job when new evidence arrives. The chip's firmware can be provisioned with address-resolution replies, Bonjour service records, filters, and keepalives. Those pieces let the system preserve enough network presence for an on-demand workstation. The heavy work still runs on the Mac after wake. The path is useful when inputs are sparse and the workstation would otherwise stay awake waiting. [ThreadX roles](rtos-threadx.md), [Sleep offload paths](sleep-network-offloads.md)

On a separately managed Mac, replay the same sensor queue against an always-awake endpoint and a sleep-and-wake endpoint. Record wake-to-first-result delay, completed jobs, hours awake, and energy over the same interval. Capture which device answered the discovery request, since a sleep proxy on the network can participate. For the established TCP case, correlate a real job request with an incoming-data wake reason and count missed-keepalive wakes separately. This measures which requests wake the host to do useful work and how often it wakes for connection maintenance. The stock firmware features and host provisioning paths are verified. An actual job-triggered wake still needs the bench. [Decoded wake reasons](sleep-network-offloads.md#keepalive-wake-reasons), [Offload verification](sleep-network-offloads.md#bench-measurements-and-use-cases)

## Align multiple views of a fast event

Let two owned cameras or sensors keep short circular buffers. Send a small identifying event over Bluetooth LE or a low-latency Wi-Fi connection. Each device preserves the window around that event and transfers evidence separately. The resulting paired views make it possible to compare a moving part before and after a processing stage without streaming the high-resolution image from every camera all the time. [Bluetooth interfaces and coexistence](bluetooth-coexistence-policy.md), [Low-latency peer paths](hp2p-low-latency.md)

Use a shared flash or other known trigger to measure the alignment. The tested kernel receive timestamps can establish where delay enters on the Mac. Over-the-air timestamps from a synchronized receiver can bound radio delay. A useful acceptance measurement is the 95th-percentile error between the two views after alignment, alongside how many events produced both recordings. Bluetooth timing, cross-device synchronization and the MAC's raw timestamp modes need their own measurements. [Timing evidence](packet-timestamps.md), [Chip-delay fields](chip-delay.md)

## Give many sensors a chance to speak at once

If cameras, vibration sensors and an inspection operator all share one access point, the Mac can coordinate when each sensor sends its next preview and reserve larger uploads for less urgent work. A controlled Wi-Fi 6 AP can schedule smaller allocations across compatible stations. Request background service for archives and compare the outcome while changing the AP's standard scheduling settings on the test network. This addresses a fleet's worst response times, where adding capacity for just one top-speed stream has limited value. [Wi-Fi 6 allocation trace](he-ofdma.md), [Service classes and WME](wifi-traffic-scheduling.md)

Use an independent receiver to verify which uplink resource assignments and priorities appeared over the air. Count each sensor's accepted previews, missed deadlines, and delivered archives. Change one policy per run so aggregation, retries, band changes, and multi-user scheduling can be attributed to the right intervention. [Aggregation and retry study](wifi-retries-and-aggregation.md), [Spatial reuse](spatial-reuse.md), [Radio-chain measurements](radio-chain-policy.md)

## Use radio changes to trigger an inspection inside a blind enclosure

Set up a dedicated transmitter and receiver across a stable path through the machine's inspection zone. Measure how the path changes when a known part moves through it. A repeatable change can trigger a short camera or vibration capture, reducing the time spent saving stationary footage. The Mac's stock signal and noise readings can start a controlled obstruction test. A separate CSI or spectrum receiver can collect the per-frequency evidence needed to test whether the method survives a changing RF environment. [Signal readings and sensing research](spectrum-sensing.md)

Use a physical part sensor as the truth reference. Test empty periods, parts of different shapes and positions, and nearby Wi-Fi traffic using held-out passes. Measure missed detections, false triggers and trigger latency. Confirmed work on this Mac establishes link measurements, channel coverage and airtime reports. Raw CSI on the BCM4378 and reliable part detection remain open. [Hardware and spectrum evidence](capability-catalog.md#radio-hardware-and-spectrum)

## Resume work after a radio fault

The recovery probe gives a transfer a random ID and verifies each 4 KiB chunk on the receiver. After a disconnect, a new authenticated connection asks how many chunks the receiver already verified and starts at that offset. The sender tries up to three connections and waits 600 ms before each retry. Previews keep their own connection. The receiver retains the verified offset in memory for this generated workload. Recovery across a process restart would require durable storage of the archive and its verified offset. [Probe source](../tools/probe_inspection_peer.swift)

Seven trials on build 26B131 verified 1 MiB each and acknowledged all 140 previews within 160 ms. The first two trials used the original transfer and the resumable transfer with no interruption. In the other trials, the receiver closed only its loopback archive socket after verifying the indicated number of chunks. Every transfer report with application data identified `lo0`. Before and after the trials, CoreWLAN reported 5 GHz primary 40 at 80 MHz and the IPv4 default interface was `en0`. [Trial data and path reports](../evidence/2026-11-17-inspection-archive-recovery.json), [Apple connection cancellation API](https://developer.apple.com/documentation/network/nwconnection/forcecancel%28%29)

| Receiver closed after verifying | Trials | Chunks sent on the new connection | Previews acknowledged between archive attempts |
| ---: | ---: | ---: | ---: |
| 1 chunk | 1 | 255 | 6 |
| 40 chunks | 3 | 216 in each trial | 6 in each trial |
| 256 chunks, before final acknowledgement | 1 | 0 | The preview workload ended before this interruption |

At the 40-chunk boundary, the new connection skipped 160 KiB the receiver had already verified. At the 256-chunk boundary, the sender only needed to recover the final acknowledgement. The timed preview acknowledgements and the receiver's resume offsets measure application recovery. Actual Wi-Fi handoff recovery still needs a paired bench with two access points. [Per-attempt offsets and byte counts](../evidence/2026-11-17-inspection-archive-recovery.json)

Use the same build as the [paired test](#test-the-direct-link-while-the-archive-is-moving) to run the local cases.

```sh
"$inspection_dir/probe_inspection_peer" selftest-resume
"$inspection_dir/probe_inspection_peer" selftest-resume 256
```

On the separate bench, use the same listener and pairing key with `run-resume`. Start with `lan` and `split` controls and compare deadline hits, per-attempt offsets, and final verified bytes during a controlled handoff. Record both bands over the air to check whether the direct link held during the router change. [Dual-band test](simultaneous-dual-band.md#keeping-an-internet-link-while-using-another-channel)

```sh
"$inspection_dir/probe_inspection_peer" run-resume "$inspection_dir/pairing.key" split en0
```

If the separate test radio reports a genuine fault during a run, keep the driver capture and correlate its time with the failed attempt. The decoded ThreadX records and driver queue evidence can then help distinguish a radio fault from a transport interruption. A single chip snapshot gives thread state at capture time. Attributing a stall needs the sequence of application, driver and radio events. [ThreadX task map](rtos-threadx.md#main-and-idle-tasks-in-the-stock-images), [Capture framing](ram-diagnostics.md), [PCIe queues](pcie-queue-sizing.md)

The [complete discovery catalog](capability-catalog.md) records the physical and firmware evidence behind these designs. The [feature index](firmware-feature-index.md) has the exact reported words and mapped driver bits.
