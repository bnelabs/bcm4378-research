# BCM4378 PCIe link and power properties

The Wi-Fi and Bluetooth PCIe functions share the `pci-bridge0` host port through an `IOPP` provider. A public I/O Kit reader matches both PCI IDs and follows their common provider. On macOS build 26B131 it read the following values. [Reader](../tools/read_pcie_link.swift), [Provider topology](../evidence/2026-11-17-pcie-function-topology.json), [Link sample](../evidence/2026-11-17-pcie-link-properties.json)

| Registry entry | Link Capabilities 2 speeds | Link Status | Rate and width decoded from status | I/O Kit current, device, max |
| --- | --- | --- | --- | --- |
| Host port `pci-bridge0` | 2.5, 5, 8, 16 GT/s | `0x1011` | 2.5 GT/s ×1 | 2, 0, 3 |
| Wi-Fi `14e4:4425` | 2.5, 5 GT/s | `0xb012` | 5 GT/s ×1 | 2, 2, 3 |
| Bluetooth `14e4:5f69` | 2.5, 5 GT/s | `0xb012` | 5 GT/s ×1 | 2, 2, 3 |

Each row held for all 13 observations over 11.56 seconds. Individual property reads agreed with the bulk `ioreg` snapshot on both sides of each read. The earlier inventory returned `0x1012` for Wi-Fi, also with speed code 2 and width 1. The port and endpoint views disagree on the rate, so the negotiated rate of the physical link needs independent confirmation. Host counters advanced on `en0` in all 12 intervals. [Earlier inventory](../evidence/2026-11-17-macos-inventory.json), [Paired reads and traffic](../evidence/2026-11-17-pcie-link-properties.json), [Standard field masks](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/pci_regs.h#L530-L610)

Apple's published implementation populates both Link Capabilities properties during enumeration. For Link Status the driver can install a serializer that reads an accessible device or refresh the cached value through a link check on an individual property lookup. The bridge can publish one status value to multiple child functions. Registry equality between the two functions provides limited evidence about independent physical behavior. The I/O Kit power-state numbers are service ordinals. [Capability publication](https://github.com/apple-oss-distributions/IOPCIFamily/blob/main/IOPCIBridge.cpp#L2992-L3009), [Status serialization and lookup](https://github.com/apple-oss-distributions/IOPCIFamily/blob/main/IOPCIDevice.cpp#L1801-L1875), [Child cache update](https://github.com/apple-oss-distributions/IOPCIFamily/blob/main/IOPCIBridge.cpp#L4698-L4717), [Host power policy](host-power-policy.md)

## Link power management

Both radio functions advertise Active State Power Management (ASPM) L1 and clock power management. The L0s support bit is clear. The port and both functions publish `pci-aspm-default = 2`, the L1 selection in the standard control mask. The Wi-Fi function and host port also publish L1 PM Substates capability fields with all four PCI-PM and ASPM L1.1 and L1.2 support bits set. The Bluetooth function has no separate substate capability property, consistent with PCIe assigning the capability to function 0 of a multifunction device. [Standard masks](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/pci_regs.h#L530-L561), [Substate masks](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/pci_regs.h#L1084-L1110), [Function 0 rule](https://github.com/torvalds/linux/blob/v6.12/drivers/pci/pcie/aspm.c#L255-L269), [Physical functions](../evidence/2026-11-17-pcie-function-topology.json)

The Wi-Fi function and port have an eight-byte `pci-l1pm-control` declaration whose first word sets all four substate enable bits. Apple's source consumes the two words as L1 substate controls subject to its support mask and policy. The two radio functions advertise Latency Tolerance Reporting (LTR) and each publishes the same `pci-max-latency` setting. Apple's enumeration code can use that setting when it has found the LTR capability. These properties establish hardware support and declarations used by the host driver. Effective link control values, L1 substate residency, exit latency, and any effect on radio service remain unmeasured. [Substate policy](https://github.com/apple-oss-distributions/IOPCIFamily/blob/main/IOPCIBridge.cpp#L1478-L1520), [LTR and ASPM initialization](https://github.com/apple-oss-distributions/IOPCIFamily/blob/main/IOPCIBridge.cpp#L3945-L4009), [LTR capability mask](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/pci_regs.h#L645-L663)

## Read the current properties

```sh
swift tools/read_pcie_link.swift
ioreg -p IOService -r -n pci-bridge0 -d 3 -w 0 | rg 'IOPCIExpressLinkStatus'
```

For a read-only comparison across OS updates, pair these values with the [host interface counters](driver-interfaces.md#passive-interface-activity) and [CoreWLAN association metrics](live-access.md). The combination records PCIe status, host traffic and Wi-Fi link conditions at the same time. Measuring link-state transitions needs separate instrumentation.
