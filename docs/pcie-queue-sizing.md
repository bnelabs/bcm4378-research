# BCM4378 packet queues and PCIe ring sizing

The running Shikoku driver publishes four numeric size properties on its `AppleBCMWLANBusInterfacePCIe` service. All four match the stock board plist on macOS 27.2.1 build 26B131. The signed driver uses those inputs for two parts of the packet path. Skywalk manages packet queues and a packet pool on the host. PCIe message rings carry descriptors between the host and the firmware. The kernel interface send scheduler is visible through a separate live readout. [Local evidence](../evidence/2026-11-17-pcie-queue-sizing.json), [Apple packet queues][apple-queues]

## Live macOS readouts

The stock `netstat -q -I en0` reported FQ-CoDel with zero packets queued and a limit of **6,720 packets**. The same scheduler and limit appeared on `awdl0`, `llw0`, `ap1` and `nan0` in separate reads. Apple's published `netstat` source obtains the values via `SIOCGIFQUEUESTATS`. XNU reads the current length and maximum length from the interface's send class queue. These are host scheduler figures. The snapshot leaves the occupancy of the DriverKit queues and PCIe rings undetermined. [Live scheduler sample](../evidence/2026-11-17-pcie-queue-sizing.json), [netstat source][netstat], [XNU dispatch][xnu-ioctl], [XNU queue readout][xnu-classq]

| Platform property | Signed plist and live registry | Use in the signed driver |
| --- | ---: | --- |
| `wlan.tx.ring.size` | 768 | Descriptor count for the default transmit completion ring and the transmit flow-ring creation path. Also supplies the fallback for the ordinary Skywalk transmit queue capacity. |
| `wlan.rx.ring.size` | 512 | Descriptor count for the receive posting and default receive completion rings. The Skywalk receive capacity is derived separately at four times this value. |
| `wlan.llw.tx.ring.size` | 512 | Input to the host transmit queue capacity for an interface with low latency enabled. |
| `wlan.tx.submission-queue.size` | 768 | Ordinary Skywalk transmit queue capacity argument when present and nonzero. The registration path passes the selected transmit capacity to both its submission and completion queue constructors. |
| `wlan.skywalk.packetpoolsize` | Absent | Optional explicit count for the shared Skywalk packet pool. The allocator computes a count when the parameter is zero. |

The four published integers match across all six installed BCM4378 board profiles. Across all 56 macOS board profiles, transmit ring sizes are 512, 768 or 1,024 and receive ring sizes are 512 or 768. The optional explicit packet-pool count appears as 9,472 in 23 profiles. All 56 profile copies under `/usr/share/firmware/wifi` are byte-identical to their counterparts in the driver bundle. [Profile comparison](../evidence/2026-11-17-pcie-queue-sizing.json)

## macOS initialization trace

`AppleBCMWLANCore::setPlatformConfigProperties` includes the five properties in its publication list. `fetchAndUpdateRingParameters` runs in both `AppleBCMWLANConfigManager::gatherParameterData` and `AppleBCMWLANCore::driverkitAllocSkywalkBusResources`. For each setting it checks a four-byte data representation and then a nonzero `OSNumber`. The initial defaults are 512 for the three ring settings and zero for the submission queue and packet pool. The authenticated call targets were matched to the named PCIe setters using the chained fixups in both `arm64e` slices. [Driver identity and symbols](../evidence/2026-11-17-pcie-queue-sizing.json)

`createStaticRings` passes the receive size to `attachRxSubmRing` and `attachDefaultRxCompRing`. It passes the transmit size to `attachDefaultTxCompRing`. `createFlow` supplies the transmit size along with a 48-byte descriptor size on its transmit flow-ring creation path. The default receive post descriptor is 32 bytes. The transmit and receive completion sizes change from 16 to 24 and from 32 to 40 bytes, respectively, when the protocol version reaches 7. The model puts the Shikoku inputs at 512 descriptors for each of those receive rings and 768 for the default transmit completion and transmit flow rings. The active protocol version, number of allocated flow rings and their occupancy were outside the live sample. [Driver trace](../evidence/2026-11-17-pcie-queue-sizing.json)

`allocateSkywalkBusResource` passes four capacity inputs to the Skywalk constructor. For Shikoku, the ordinary transmit capacity is the configured submission queue value. The low-latency transmit capacity is `2 × (low-latency input + 256)`. The receive capacity is four times the receive input. With no explicit pool size, the allocator adds four ordinary transmit capacities, half the low-latency capacity, twice the receive capacity and 512. The resulting constructor arguments are **768 ordinary transmit, 1,536 low-latency transmit, 2,048 receive and 8,448 pool entries**. These are calculations from the published inputs and the signed code. The low-latency queue is selected by the interface's low-latency flag during registration. The calculation leaves the set of queues allocated by each running role open. [Static data flow](../evidence/2026-11-17-pcie-queue-sizing.json), [DriverKit queue definitions][apple-queues]

## Linux and Asahi

Stable Linux `v7.3.4` and Asahi `asahi-7.3.4-2` accept PCIe shared-protocol versions 5 through 7. The host allocates five common DMA rings using the table below. It reads ring counts and the maximum number of posted receive buffers from firmware. The latter is a separate limit on the buffer refill path and defaults to 255 if firmware supplies zero. Both drivers can keep indices in host DMA memory when firmware advertises support and allocation succeeds. Their fallback keeps indices in device memory. [Stable PCIe source][stable-pcie], [Asahi PCIe source][asahi-pcie], [Firmware limits][shared-limits], [Receive refill][rx-fill]

| Ring | Stable entries | Asahi entries | Bytes per descriptor at v5–6 / v7 |
| --- | ---: | ---: | ---: |
| Control submission | 64 | 64 | 40 / 40 |
| Receive posting | 1,024 | 2,048 | 32 / 32 |
| Control completion | 64 | 64 | 24 / 24 |
| Transmit completion | 1,024 | 1,024 | 16 / 24 |
| Receive completion | 1,024 | 2,048 | 32 / 40 |
| Per transmit flow, allocated on demand | 512 | 512 | 48 / 48 |

Asahi also increases the receive packet-ID table from 1,024 to 2,048. Its commit cites BCM4388 firmware using more than 1,024 posted receive buffers. The two larger ring constants are shared by the PCIe build, including its BCM4378 path. A BCM4378-specific buffer requirement and performance difference remain unmeasured. At protocol v7 the five common rings account for 100 KiB of descriptor storage on stable and 172 KiB on Asahi, before backing packet buffers, indices and per-flow rings. [Stable constants][stable-depth], [Asahi constants][asahi-depth], [Asahi change][asahi-rx-change], [Flow-ring allocation][flow-alloc]

On a bench Linux system with the relevant debug build and wiphy debugfs available, `msgbuf_stats` prints the five common ring depths, cached read/write indices, and software queue lengths and blocked flags for open transmit flows. The callback reads host driver structures. Retained excerpts should omit the peer MAC addresses in its per-flow output. This readout provides a way to compare host queue pressure with round-trip latency and link telemetry on an owned test link. The code and measurements here leave live firmware register values and chip RAM access open. [Stable readout][stable-stats], [Asahi readout][asahi-stats], [Firmware RAM diagnostics](ram-diagnostics.md)

## Reproduce the macOS observations

```sh
python3 tools/read_macos_inventory.py
/usr/sbin/netstat -q -I en0
python3 tools/inspect_firmware.py \
  /usr/share/firmware/wifi/C-4378__s-B1/shikoku.trx \
  --platform-config /usr/share/firmware/wifi/shikoku-PlatformConfig.plist
```

The first command reports the whitelist of published PCIe transport integers under `wifi.transport_config_properties`. The second reports the kernel send scheduler. The third reads only installed files. The static checks use `xcrun llvm-objdump --macho --disassemble --dis-symname` with the listed functions and `xcrun dyld_info -fixups` for each driver slice. [Inventory reader](../tools/read_macos_inventory.py), [Firmware reader](../tools/inspect_firmware.py)

[apple-queues]: https://developer.apple.com/documentation/networkingdriverkit/iousernetworkpacketqueue
[netstat]: https://github.com/apple-oss-distributions/network_cmds/blob/97e27e6244c16d399bfeb254315ddc5828711c56/netstat.tproj/if.c#L1444-L1487
[xnu-ioctl]: https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/net/if.c#L2097-L2124
[xnu-classq]: https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/net/classq/classq_subr.c#L557-L587
[stable-depth]: https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.h#L10-L24
[asahi-depth]: https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.h#L10-L24
[stable-pcie]: https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L1218-L1356
[asahi-pcie]: https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L1376-L1514
[shared-limits]: https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L1781-L1820
[rx-fill]: https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.c#L1047-L1079
[flow-alloc]: https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.c#L620-L657
[asahi-rx-change]: https://github.com/AsahiLinux/linux/commit/97bea96039a67ab13c8b062ffb26afb243bfd583
[stable-stats]: https://github.com/gregkh/linux/blob/7595a62d45ee1a2297eafa5f2ef5d0a45142d84d/drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.c#L1503-L1560
[asahi-stats]: https://github.com/AsahiLinux/linux/blob/201be96df5654336bdcbe1da2103f193d7a0b940/drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.c#L1588-L1645
