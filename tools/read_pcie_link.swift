import Foundation
import IOKit

enum ReadError: Error {
    case missingService(String)
    case missingParent
    case unexpectedTopology
}

func property(_ key: String, on entry: io_registry_entry_t) -> Any? {
    IORegistryEntryCreateCFProperty(entry, key as CFString, kCFAllocatorDefault, 0)?
        .takeRetainedValue()
}

func words(_ data: Data) -> [UInt32] {
    guard data.count.isMultiple(of: 4) else { return [] }
    return stride(from: data.startIndex, to: data.endIndex, by: 4).map { offset in
        data[offset..<(offset + 4)].reversed().reduce(0) { ($0 << 8) | UInt32($1) }
    }
}

func pciID(_ entry: io_registry_entry_t) -> String? {
    guard let vendor = property("vendor-id", on: entry) as? Data,
          let device = property("device-id", on: entry) as? Data,
          vendor.count == 4, device.count == 4,
          let vendorID = words(vendor).first, let deviceID = words(device).first else {
        return nil
    }
    return String(format: "%04x:%04x", vendorID, deviceID)
}

func service(_ name: String, pciID expected: String) throws -> io_registry_entry_t {
    var iterator: io_iterator_t = 0
    let status = IOServiceGetMatchingServices(kIOMainPortDefault, IOServiceNameMatching(name), &iterator)
    guard status == KERN_SUCCESS else { throw ReadError.missingService(name) }
    defer { IOObjectRelease(iterator) }
    while true {
        let entry = IOIteratorNext(iterator)
        guard entry != 0 else { throw ReadError.missingService(name) }
        if pciID(entry) == expected { return entry }
        IOObjectRelease(entry)
    }
}

func parent(of entry: io_registry_entry_t) throws -> io_registry_entry_t {
    var parent: io_registry_entry_t = 0
    guard IORegistryEntryGetParentEntry(entry, kIOServicePlane, &parent) == KERN_SUCCESS else {
        throw ReadError.missingParent
    }
    return parent
}

func name(of entry: io_registry_entry_t) -> String {
    var name = [CChar](repeating: 0, count: 128)
    guard IORegistryEntryGetName(entry, &name) == KERN_SUCCESS else { return "" }
    return String(decoding: name.prefix { $0 != 0 }.map { UInt8(bitPattern: $0) }, as: UTF8.self)
}

func readLink(_ entry: io_registry_entry_t) -> [String: Any] {
    let numericKeys = [
        "IOPCIExpressLinkStatus", "IOPCIExpressLinkCapabilities", "IOPCIExpressLinkCapabilities2",
        "IOPCIExpressDeviceCapabilities2", "IOPCIL1PMCapabilities", "pci-aspm-default",
    ]
    var result: [String: Any] = ["name": name(of: entry)]
    result["pci_id"] = pciID(entry)
    for key in numericKeys {
        if let value = property(key, on: entry) as? NSNumber {
            result[key] = String(format: "0x%x", value.uint32Value)
        }
    }
    for (key, count) in [("pci-l1pm-control", 8), ("pci-max-latency", 4)] {
        if let value = property(key, on: entry) as? Data, value.count == count {
            result[key] = words(value).map { String(format: "0x%x", $0) }
        }
    }
    if let power = property("IOPowerManagement", on: entry) as? [String: Any] {
        let keys = ["CurrentPowerState", "DevicePowerState", "MaxPowerState"]
        result["IOPowerManagement"] = keys.reduce(into: [String: UInt32]()) { states, key in
            states[key] = (power[key] as? NSNumber)?.uint32Value
        }
    }
    return result
}

func snapshot() throws -> [String: Any] {
    let wifi = try service("wlan", pciID: "14e4:4425")
    defer { IOObjectRelease(wifi) }
    let bluetooth = try service("bluetooth-pcie", pciID: "14e4:5f69")
    defer { IOObjectRelease(bluetooth) }
    let wifiProvider = try parent(of: wifi)
    defer { IOObjectRelease(wifiProvider) }
    let bluetoothProvider = try parent(of: bluetooth)
    defer { IOObjectRelease(bluetoothProvider) }
    guard IOObjectIsEqualTo(wifiProvider, bluetoothProvider) != 0 else {
        throw ReadError.unexpectedTopology
    }
    let bridge = try parent(of: wifiProvider)
    defer { IOObjectRelease(bridge) }
    guard IOObjectConformsTo(bridge, "IOPCIDevice") != 0 else {
        throw ReadError.unexpectedTopology
    }

    return [
        "sampled_at_unix_seconds": Date().timeIntervalSince1970,
        "bridge": readLink(bridge),
        "wifi": readLink(wifi),
        "bluetooth": readLink(bluetooth),
    ]
}

do {
    let data = try JSONSerialization.data(withJSONObject: snapshot(), options: [.prettyPrinted, .sortedKeys])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data([0x0a]))
} catch {
    FileHandle.standardError.write(Data("Could not read the BCM4378 PCIe topology (\(error)).\n".utf8))
    exit(1)
}
