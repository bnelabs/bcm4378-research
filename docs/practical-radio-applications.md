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

With an owned camera or phone, the next version would carry the preview on a separate connection and record the part ID and age at the receiver. The Mac can request an Apple peer link for local camera traffic and use its ordinary router connection for archive upload. The A2337 lab result and firmware's dual-band flag support testing that combination. The exact route, band and airtime of an app's transfer need verification. Measure how many previews reach the inspection decision within the part's time window, how many complete images remain in the archive, and whether the preview yields the same decision as the full image. [Peer roles](driver-interfaces.md#running-wi-fi-interfaces), [Dual-band gates](simultaneous-dual-band.md)

The receiver's deadline misses can drive the sender to lower archive pacing or use smaller previews. The published same-network, other-network, and interference readings can help explain the circumstances after the fact. In one 22-second run the connected Mac returned 18% average and 7% other-network CCA at every read. Decisions about immediate rate need the receiver's delivery times because the CCA values can persist across snapshots. [Live airtime values](live-wifi-airtime.md)

Two small HTTPS transfers on this Mac showed that the inspection socket setting can be visible at only part of the path. The video class advanced the tunnel queue while the Wi-Fi video queue and radio's video counters stayed flat. Keep the preview deadline in the sender and receiver, and check physical queue behavior wherever the inspection system is deployed. [Measured tunnel and Wi-Fi queues](wifi-traffic-scheduling.md#where-interactive-priority-showed-up-on-the-connected-mac)

For a portable inspection kit, use the stock country tables to choose a shared 80 MHz block and narrower fallbacks for the camera and Mac. For example, the installed Türkiye, US and Japan rows all contain the block centered at 5,210 MHz. The 80 MHz block containing channel 144 appears in the US and Japan rows and is absent under Türkiye's rules for this Mac. Confirm the owned access point's available settings and the Mac's active list at the site. Record the negotiated width with the preview deadline results so changes to the radio plan can inform the sender's pacing. [Field deployment example and decoder](clm-channel-tables.md#plan-an-access-point-before-a-field-deployment)

## Wake the Mac when inspection work actually arrives

An owned sensor can hold a small work queue while the Mac sleeps, discover the service over the local network, and submit an analysis job when new evidence arrives. The chip's firmware can be provisioned with address-resolution replies, Bonjour service records, filters, and keepalives. Those pieces let the system preserve enough network presence for an on-demand workstation. The heavy work still runs on the Mac after wake. The path is useful when inputs are sparse and the workstation would otherwise stay awake waiting. [ThreadX roles](rtos-threadx.md), [Sleep offload paths](sleep-network-offloads.md)

On a separately managed Mac, replay the same sensor queue against an always-awake endpoint and a sleep-and-wake endpoint. Record wake-to-first-result delay, completed jobs, hours awake, and energy over the same interval. Capture which device answered the discovery request, since a sleep proxy on the network can participate. The stock firmware features and host provisioning functions are known. Actual responses during sleep remain unmeasured on the research Mac. [Offload verification](sleep-network-offloads.md#bench-measurements-and-use-cases)

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

An inspection sender can assign a stable ID to each archive and acknowledge completed chunks. When the link returns, the two devices resume the same job from the last committed chunk. An owned test radio can supply a retained RAM capture if a real fault occurs. The decoded ThreadX records and driver queue evidence can then help distinguish an interrupted application transfer from a failure that occurred inside the chip. A single snapshot gives thread state at capture time. Attributing a stall needs the sequence of application, driver and radio events. [ThreadX task map](rtos-threadx.md#main-and-idle-tasks-in-the-stock-images), [Capture framing](ram-diagnostics.md), [PCIe queues](pcie-queue-sizing.md)

The [complete discovery catalog](capability-catalog.md) records the physical and firmware evidence behind these designs. The [feature index](firmware-feature-index.md) has the exact reported words and mapped driver bits.
