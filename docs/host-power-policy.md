# macOS host power policy and Wi-Fi

On 17 November 2026 the M1 MacBook Air was on AC power. Its live settings matched the stored AC profile for the fields below. The bundled `pmset(1)` manual describes `-g live` as the current settings, `-g custom` as settings by power source, `-g cap` as reported capabilities, and `-g ps` as power source status. The sample retains only selected policy values, capability names, and the active power source. [Power-policy snapshot](../evidence/2026-11-17-macos-host-power-policy.json)

| `pmset` field | AC and live | Battery | Scope |
| --- | ---: | ---: | --- |
| `womp` | 1 | 0 | Wake for network access. The manual names an Ethernet magic packet and links the setting to the host's network-wake policy. Apple describes waking for shared resources with a supported wireless setup. [Apple network wake guidance](https://support.apple.com/en-gb/guide/mac-help/mh27905/mac), [Apple setting map](https://github.com/apple-oss-distributions/PowerManagement/blob/d415e45501842834a280930c3eed9186544a67f0/pmset/pmset.m#L307-L331) |
| `tcpkeepalive` | 1 | 1 | Host preference for TCP keepalive during system sleep. A saved value of 1 leaves connection continuity and any radio offload unmeasured. [Apple preference and sleep description](https://github.com/apple-oss-distributions/PowerManagement/blob/d415e45501842834a280930c3eed9186544a67f0/pmset/pmset.m#L5796-L5806) |
| `networkoversleep` | 0 | 0 | The bundled manual associates this setting with shared-service presentation during sleep and says it is used on some platforms. Its effect on this Mac remains unverified. |
| `powernap` | 1 | 1 | Apple's `pmset` source maps this field to a background-task power policy. The field appeared in this Mac's capability list. Apple's Power Nap guide limits the Settings option to Intel Macs. Background-task execution during sleep on this M1 remains unverified. [Apple setting map](https://github.com/apple-oss-distributions/PowerManagement/blob/d415e45501842834a280930c3eed9186544a67f0/pmset/pmset.m#L322-L333), [Apple Power Nap guidance](https://support.apple.com/en-ie/guide/mac-help/mh40774/mac) |
| `lowpowermode` | 0 | 1 | Host Low Power Mode preference. [Apple Battery settings](https://support.apple.com/en-au/guide/mac-help/mchlfc3b7879/mac) |
| `sleep` | 1 min | 1 min | System idle timer. Power assertions can affect when the host sleeps. |
| `displaysleep` | 10 min | 2 min | Display idle timer. [Apple Mac sleep settings](https://support.apple.com/en-ie/guide/mac-help/mchle41a6ccd/27/mac/27) |

The configured AC network-wake policy leaves the wake trigger and result on this network unmeasured. The sample contains no wake attempt or sleep interval.

## Registry power states

The sample used the public I/O Registry property getter to read `IOPowerManagement` on two entries in the Wi-Fi stack. The bundled `pmset(1)` manual also documents `-g powerstate` for current I/O Kit driver states. Apple describes a per-driver state array, and the XNU serializer calculates `MaxPowerState` from the number of states. The ordinals apply to the named entry's I/O Kit power management. [Registry property getter](https://developer.apple.com/documentation/iokit/1514293-ioregistryentrycreatecfproperty/), [Apple I/O Kit power management](https://developer.apple.com/library/archive/documentation/DeviceDrivers/Conceptual/IOKitFundamentals/PowerMgmt/PowerMgmt.html), [XNU serializer](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/iokit/Kernel/IOServicePM.cpp#L9489-L9504)

| Entry | Registry class | Current | Device | Maximum |
| --- | --- | ---: | ---: | ---: |
| `wlan` | `IOPCIDevice` | 2 | 2 | 3 |
| `AppleBCMWLANCore` | `IOUserService` | 3 | — | 3 |

The Wi-Fi and Bluetooth PCIe functions (`14e4:4425` and `14e4:5f69`) are siblings. The `wlan` and `AppleBCMWLANCore` observations cover the Wi-Fi function and its driver service. The WLAN-labeled serial endpoint `wlan-debug` has a separate host UART2 provider. [PCIe topology](../evidence/2026-11-17-pcie-function-topology.json), [Serial topology](../evidence/2026-11-17-wlan-serial-registry.json)

## Radio power and scheduling

CoreWLAN's `powerOn()` getter queries the interface's Boolean power state. Apple documents `false` on error. This readout describes the host WLAN interface. [CoreWLAN power getter](https://developer.apple.com/documentation/corewlan/cwinterface/poweron%28%29)

Apple's router guidance describes WMM as traffic prioritization. The IEEE 802.11 working group describes Target Wake Time as a Wi-Fi power-save scheduling mechanism. The host policy and registry readings leave link-level WMM Power Save, an active TWT schedule, and the BCM4378's RF doze duty cycle unmeasured. The earlier timing investigation recorded static driver markers and left live TWT scheduling unverified. [Apple WMM guidance](https://support.apple.com/en-us/102766), [IEEE 802.11 timing liaison](https://www.ieee802.org/11/Liaisons/2022-12-20-802-11%20liaison%20to%20802-1%20re%20TSN%20support.pdf), [Timing evidence](../evidence/2026-11-17-wifi-timing-capabilities.json)

The live PCIe service publishes the low-power associated-sleep permission, and the firmware advertises `lpas`. The driver uses both inputs before requesting the mode. Its beacon-based wake path also calculates an extended DTIM count. [Radio power and wake scheduling](radio-power-scheduling.md)
