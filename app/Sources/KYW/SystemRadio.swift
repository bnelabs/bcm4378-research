import CoreWLAN
import CryptoKit
import Darwin
import Foundation
import IOKit
import SystemConfiguration

struct KYWError: LocalizedError {
    let message: String
    init(_ message: String) { self.message = message }
    var errorDescription: String? { message }
}

enum ToolRunner {
    static func temporaryDirectory() throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("KYW-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700]
        )
        return directory
    }

    static func run(
        _ executable: URL, _ arguments: [String] = [], timeout: TimeInterval = 12,
        combineOutput: Bool = false
    ) throws -> Data {
        guard FileManager.default.isExecutableFile(atPath: executable.path) else {
            throw KYWError("\(executable.lastPathComponent) is unavailable.")
        }
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let output = directory.appendingPathComponent("output")
        let errors = directory.appendingPathComponent("errors")
        try Data().write(to: output)
        try Data().write(to: errors)
        let stdout = try FileHandle(forWritingTo: output)
        let stderr = try FileHandle(forWritingTo: errors)
        defer {
            try? stdout.close()
            try? stderr.close()
        }

        let process = Process()
        let stopped = DispatchSemaphore(value: 0)
        process.executableURL = executable
        process.arguments = arguments
        process.standardOutput = stdout
        process.standardError = combineOutput ? stdout : stderr
        process.standardInput = FileHandle.nullDevice
        process.terminationHandler = { _ in stopped.signal() }
        try process.run()
        if stopped.wait(timeout: .now() + timeout) == .timedOut {
            if process.isRunning { process.terminate() }
            if stopped.wait(timeout: .now() + 1) == .timedOut, process.isRunning {
                kill(process.processIdentifier, SIGKILL)
                _ = stopped.wait(timeout: .now() + 1)
            }
            throw KYWError("\(executable.lastPathComponent) timed out.")
        }
        if process.terminationStatus != 0 {
            let details = (try? String(contentsOf: combineOutput ? output : errors, encoding: .utf8))?
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if let details, !details.isEmpty {
                throw KYWError(String(details.prefix(600)))
            }
            throw KYWError("\(executable.lastPathComponent) exited with status \(process.terminationStatus).")
        }
        return try Data(contentsOf: output)
    }

    static func system(_ path: String, _ arguments: [String] = [], timeout: TimeInterval = 12) throws -> Data {
        try run(URL(fileURLWithPath: path), arguments, timeout: timeout)
    }
}

enum Resources {
    static var folder: URL {
        Bundle.main.resourceURL ?? Bundle.main.bundleURL.appendingPathComponent("Contents/Resources")
    }

    static func helper(_ name: String) -> URL {
        Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers", isDirectory: true)
            .appendingPathComponent(name)
    }

    static func python(_ script: String, _ args: [String]) throws -> Data {
        let pythonPaths = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]
        guard let python = pythonPaths.first(where: FileManager.default.isExecutableFile(atPath:)) else {
            throw KYWError("Install Python 3 to use the bundled offline research tools.")
        }
        let executable = folder.appendingPathComponent("Tools").appendingPathComponent(script)
        guard FileManager.default.isReadableFile(atPath: executable.path) else {
            throw KYWError("Rebuild KYW to include its bundled research tools.")
        }
        return try ToolRunner.run(
            URL(fileURLWithPath: python), ["-B", executable.path] + args, timeout: 35
        )
    }
}

enum SystemRadio {
    private static let client = CWWiFiClient.shared()
    private static let widths: [CWChannelWidth: Int] = [
        .width20MHz: 20, .width40MHz: 40, .width80MHz: 80, .width160MHz: 160
    ]
    private static let bands: [CWChannelBand: Band] = [.band2GHz: .two, .band5GHz: .five, .band6GHz: .six]
    private static let physics: [CWPHYMode: String] = [
        .mode11a: "802.11a", .mode11b: "802.11b", .mode11g: "802.11g", .mode11n: "802.11n",
        .mode11ac: "Wi-Fi 5", .mode11ax: "Wi-Fi 6", .mode11be: "Wi-Fi 7"
    ]

    private static func channel(_ value: CWChannel) -> RadioChannel? {
        guard let band = bands[value.channelBand], let width = widths[value.channelWidth] else { return nil }
        return RadioChannel(band: band, number: value.channelNumber, width: width)
    }

    private static func text(_ path: String, _ arguments: [String]) -> String {
        guard let data = try? ToolRunner.system(path, arguments, timeout: 4) else { return "" }
        return String(decoding: data, as: UTF8.self)
    }

    static func defaultRoutes() throws -> [String] {
        var names = Set<String>()
        for family in ["-inet", "-inet6"] {
            let output: Data
            do {
                output = try ToolRunner.run(
                    URL(fileURLWithPath: "/sbin/route"),
                    ["-n", "get", family, "default"], timeout: 4, combineOutput: true
                )
            } catch let error as KYWError where error.message.contains("routing socket: not in table") {
                continue
            }
            let route = String(decoding: output, as: UTF8.self)
            let lines = route.split(separator: "\n").map { $0.split(whereSeparator: \.isWhitespace) }
            if let fields = lines.first(where: { $0.count == 2 && $0[0] == "interface:" }) {
                names.insert(String(fields[1]))
            } else if !route.contains("not in table") {
                throw KYWError("macOS did not identify the default route for \(family == "-inet" ? "IPv4" : "IPv6").")
            }
        }
        return names.sorted()
    }

    private static func wiredInterfaces() -> Set<String> {
        let interfaces = SCNetworkInterfaceCopyAll() as? [SCNetworkInterface] ?? []
        return Set(interfaces.compactMap { interface in
            guard SCNetworkInterfaceGetInterfaceType(interface) == kSCNetworkInterfaceTypeEthernet else { return nil }
            return SCNetworkInterfaceGetBSDName(interface) as String?
        })
    }

    private static func driverCountry(interfaceName: String?) -> String? {
        guard let interfaceName else { return nil }
        var iterator: io_iterator_t = 0
        guard IOServiceGetMatchingServices(kIOMainPortDefault, IOServiceMatching("IOUserNetworkWLAN"), &iterator)
                == KERN_SUCCESS else { return nil }
        defer { IOObjectRelease(iterator) }
        while case let service = IOIteratorNext(iterator), service != 0 {
            defer { IOObjectRelease(service) }
            func property(_ key: String) -> CFTypeRef? {
                IORegistryEntryCreateCFProperty(service, key as CFString, kCFAllocatorDefault, 0)?.takeRetainedValue()
            }
            guard let prefix = property("IOInterfaceNamePrefix") as? String,
                  let unit = property("IOInterfaceUnit") as? Int, "\(prefix)\(unit)" == interfaceName else { continue }
            return property("IO80211CountryCode") as? String
        }
        return nil
    }

    static func radioPermission(
        interface: String?, associated: Bool, routes: [String], wired: Set<String>
    ) -> (Bool, String) {
        guard let interface else { return (false, "macOS found no controllable Wi-Fi interface.") }
        guard !associated, !routes.contains(interface) else {
            return (false, "Wi-Fi is carrying a connection. Use a separate, Ethernet-managed Mac for radio changes.")
        }
        guard !routes.isEmpty, Set(routes).isSubset(of: wired) else {
            return (false, "A verified Ethernet route is needed before changing a detached Wi-Fi radio.")
        }
        return (true, "Wi-Fi is detached and Ethernet is carrying the default route.")
    }

    static func status() -> LinkStatus {
        let interface = client.interface()
        let current = interface?.wlanChannel().flatMap(channel)
        let mode = interface?.interfaceMode() ?? .none
        let routes = try? defaultRoutes()
        let associated = mode != .none
        let wired = associated ? [] : wiredInterfaces()
        let permission = radioPermission(
            interface: interface?.interfaceName, associated: associated, routes: routes ?? [], wired: wired
        )
        let available = (interface?.supportedWLANChannels() ?? []).compactMap(channel)
            .sorted { ($0.band.rawValue, $0.width, $0.number) < ($1.band.rawValue, $1.width, $1.number) }
        let rssi = interface?.rssiValue() ?? 0
        let noise = interface?.noiseMeasurement() ?? 0
        let rate = interface?.transmitRate() ?? 0
        let power = interface?.transmitPower() ?? 0
        return LinkStatus(
            measuredAt: Date(), interface: interface?.interfaceName,
            mode: [.none: "Detached", .station: "Station", .IBSS: "Ad hoc", .hostAP: "Access point"][mode] ?? "Other",
            powerOn: interface?.powerOn() ?? false, channel: current, rssi: rssi < 0 ? rssi : nil,
            noise: noise < 0 ? noise : nil, rate: rate > 0 && rate.isFinite ? rate : nil,
            osPowerValue: power > 0 ? power : nil, phy: interface.flatMap { physics[$0.activePHYMode()] },
            country: interface?.countryCode().flatMap { $0.isEmpty ? nil : $0 }
                ?? driverCountry(interfaceName: interface?.interfaceName),
            routes: routes ?? [], channels: available,
            canChangeRadio: permission.0, radioControlReason: permission.1
        )
    }

    static func reading() -> RadioReading {
        let link = status()
        let executable = Resources.helper("read_wifi_airtime")
        let airtime = try? AppData.decode(ReportSample.self, ToolRunner.run(executable))
        let channelData = try? ToolRunner.run(executable, ["--channel-switch"])
        let channels = channelData.flatMap { try? AppData.decode(ReportSample.self, $0) }
        let notice = airtime == nil || channels == nil ? "The WLAN reporter is unavailable for some measurements." : nil
        return RadioReading(status: link, airtime: airtime, channels: channels, rawChannels: channelData, reportNotice: notice)
    }

    enum Change: Sendable {
        case power(Bool), channel(RadioChannel)
    }

    static func apply(_ change: Change) throws {
        guard let interface = client.interface() else {
            throw KYWError("macOS found no controllable Wi-Fi interface.")
        }
        let routes = try defaultRoutes()
        let wired = wiredInterfaces()
        let permission = radioPermission(
            interface: interface.interfaceName,
            associated: interface.interfaceMode() != .none,
            routes: routes, wired: wired
        )
        guard permission.0 else { throw KYWError(permission.1) }

        switch change {
        case .power(let value):
            try interface.setPower(value)
        case .channel(let choice):
            guard interface.powerOn() else { throw KYWError("Turn on the detached radio to select a channel.") }
            guard let target = interface.supportedWLANChannels()?.first(where: { channel($0) == choice }) else {
                throw KYWError("macOS currently omits this channel from its supported list.")
            }
            try interface.setWLANChannel(target)
        }
    }

    private static func capture(pattern: String, in text: String) -> String? {
        guard let match = try? NSRegularExpression(pattern: pattern).firstMatch(
            in: text, range: NSRange(text.startIndex..., in: text)
        ), let range = Range(match.range(at: 1), in: text) else { return nil }
        return String(text[range])
    }

    private static func registryNodes(_ entry: [String: Any]) -> [[String: Any]] {
        [entry] + (entry["IORegistryEntryChildren"] as? [[String: Any]] ?? []).flatMap(registryNodes)
    }

    private static func stockFile(_ relative: String?) -> URL? {
        guard let relative, !relative.hasPrefix("/"),
              !relative.split(separator: "/").contains("..") else { return nil }
        let base = URL(fileURLWithPath: "/usr/share/firmware/wifi", isDirectory: true)
        let file = base.appendingPathComponent(relative)
        return FileManager.default.isReadableFile(atPath: file.path) ? file : nil
    }

    private static func rtos(for digest: String) -> String? {
        let evidence = Resources.folder.appendingPathComponent("Evidence/2026-11-17-threadx-firmware.json")
        guard let data = try? Data(contentsOf: evidence),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let images = object["images"] as? [[String: Any]] else { return nil }
        for image in images {
            guard let file = image["file"] as? [String: Any], file["sha256"] as? String == digest,
                  let banner = image["initialization_log"] as? [String: Any],
                  let major = banner["major_in_r1"] as? Int, let minor = banner["minor_in_r2"] as? Int else { continue }
            return "ThreadX \(major).\(minor)"
        }
        return nil
    }

    static func identity() throws -> HardwareIdentity {
        let plist = try ToolRunner.system("/usr/sbin/ioreg", ["-a", "-l", "-p", "IOService", "-r", "-n", "wlan", "-d", "6"])
        let raw = try PropertyListSerialization.propertyList(from: plist, options: [], format: nil)
        let nodes = (raw as? [[String: Any]] ?? []).flatMap(registryNodes)
        let core = nodes.first { $0["IORegistryEntryName"] as? String == "AppleBCMWLANCore" } ?? [:]
        let pci = nodes.first { $0["device-id"] is Data && $0["vendor-id"] is Data } ?? [:]
        let requested = (core["RequestedFiles"] as? [[String: String]])?.first ?? [:]
        let firmware = stockFile(requested["Firmware"])
        let firmwareBytes = firmware.flatMap { try? Data(contentsOf: $0, options: .mappedIfSafe) }
        let digest = firmwareBytes.map { SHA256.hash(data: $0).map { String(format: "%02x", $0) }.joined() }
        let version = core["FirmwareVersion"] as? String ?? ""
        let pciID: String?
        if let vendor = pci["vendor-id"] as? Data, let device = pci["device-id"] as? Data,
           vendor.count >= 2, device.count >= 2 {
            pciID = String(format: "%02x%02x:%02x%02x", vendor[1], vendor[0], device[1], device[0])
        } else {
            pciID = nil
        }
        let roles = nodes.compactMap { node -> InterfaceRole? in
            guard node["IOObjectClass"] as? String == "IOUserNetworkWLAN",
                  let prefix = node["IOInterfaceNamePrefix"] as? String,
                  let unit = node["IOInterfaceUnit"] as? Int else { return nil }
            let role = (node["IO80211VirtualInterfaceRole"] ?? node["IO80211InterfaceRole"]) as? String
            return InterfaceRole(name: "\(prefix)\(unit)", role: role ?? "Wi-Fi")
        }.sorted { $0.name < $1.name }
        let words = (core["FWCap"] as? String ?? "").split(whereSeparator: \.isWhitespace).map(String.init)
        return HardwareIdentity(
            model: text("/usr/sbin/sysctl", ["-n", "hw.model"]).trimmingCharacters(in: .whitespacesAndNewlines),
            systemVersion: ProcessInfo.processInfo.operatingSystemVersionString,
            chip: (core["ChipSet"] as? Int).map { "Broadcom BCM\($0)" },
            chipRevision: requested["Firmware"].flatMap { capture(pattern: "__s-([A-Za-z0-9]+)/", in: $0) },
            pciID: pciID, board: requested["Firmware"].map {
                URL(fileURLWithPath: $0).deletingPathExtension().lastPathComponent
            },
            firmware: capture(pattern: "version ([0-9.]+)", in: version),
            firmwareID: capture(pattern: "FWID ([0-9a-fA-F-]+)", in: version),
            firmwarePath: firmware?.path, resolvedFirmwarePath: firmware?.resolvingSymlinksInPath().path,
            firmwareDigest: digest, threadX: digest.flatMap(rtos(for:)),
            regulatoryPath: stockFile(requested["Regulatory"])?.path,
            boardSettingsPath: stockFile(requested["NVRAM"])?.path, powerCapsPath: stockFile(requested["TxCap"])?.path,
            capabilities: words, roles: roles
        )
    }
}
