import CoreWLAN
import Foundation

let client = CWWiFiClient.shared()
guard let wifi = client.interface() else {
    FileHandle.standardError.write(Data("CoreWLAN found no Wi-Fi interface.\n".utf8))
    exit(1)
}

struct InterfaceTraffic: Encodable {
    let sampled_at_unix_seconds: Double
    let rx_bytes: UInt64
    let tx_bytes: UInt64
    let rx_packets: UInt64
    let tx_packets: UInt64
}

struct WiFiStatus: Encodable {
    let interface: String?
    let api_visible_interfaces: [String]?
    let interface_mode: String
    let radio_power_on: Bool
    let phy_mode: String
    let band: String?
    let channel: Int?
    let channel_width_mhz: Int?
    let rssi_dbm: Int?
    let noise_dbm: Int?
    let tx_rate_mbps: Double?
    let corewlan_transmit_power: Int?
    let sampled_at_unix_seconds: Double
    let host_thermal_state: String?
    let interface_traffic: InterfaceTraffic?
    let reported_channel_widths_mhz_by_band: [String: [Int]]?
    let reported_channel_numbers_by_band_and_width_mhz: [String: [Int: [Int]]]?
}

let phyNames: [CWPHYMode: String] = [
    .mode11a: "802.11a", .mode11b: "802.11b", .mode11g: "802.11g",
    .mode11n: "802.11n", .mode11ac: "802.11ac", .mode11ax: "802.11ax",
    .mode11be: "802.11be",
]
let channelWidths: [CWChannelWidth: Int] = [
    .width20MHz: 20, .width40MHz: 40, .width80MHz: 80, .width160MHz: 160,
]
let bandNames: [CWChannelBand: String] = [
    .band2GHz: "2.4 GHz", .band5GHz: "5 GHz", .band6GHz: "6 GHz",
]
let modeNames: [CWInterfaceMode: String] = [
    .none: "none", .station: "station", .IBSS: "IBSS", .hostAP: "host AP",
]

func channelsByBandAndWidth(_ channels: Set<CWChannel>) -> [String: [Int: [Int]]] {
    var channelsByBand: [String: [Int: Set<Int>]] = [:]
    for channel in channels {
        if let band = bandNames[channel.channelBand], let width = channelWidths[channel.channelWidth] {
            channelsByBand[band, default: [:]][width, default: []].insert(channel.channelNumber)
        }
    }
    return channelsByBand.mapValues { $0.mapValues { $0.sorted() } }
}

func parseInterfaceTraffic(_ output: String, interfaceName: String, sampledAt: Double) -> InterfaceTraffic? {
    let lines = output.split(whereSeparator: \.isNewline)
    guard let header = lines.first?.split(whereSeparator: \.isWhitespace),
          let name = header.firstIndex(of: "Name"),
          let network = header.firstIndex(of: "Network"),
          let receivedBytes = header.firstIndex(of: "Ibytes"),
          let sentBytes = header.firstIndex(of: "Obytes"),
          let receivedPackets = header.firstIndex(of: "Ipkts"),
          let sentPackets = header.firstIndex(of: "Opkts") else { return nil }

    for line in lines.dropFirst() {
        let row = line.split(whereSeparator: \.isWhitespace)
        guard row.count == header.count,
              row[name] == interfaceName || row[name] == "\(interfaceName)*",
              row[network].hasPrefix("<Link#"), row[network].hasSuffix(">"),
              let rxBytes = UInt64(row[receivedBytes]), let txBytes = UInt64(row[sentBytes]),
              let rxPackets = UInt64(row[receivedPackets]), let txPackets = UInt64(row[sentPackets]) else {
            continue
        }
        return InterfaceTraffic(
            sampled_at_unix_seconds: sampledAt,
            rx_bytes: rxBytes,
            tx_bytes: txBytes,
            rx_packets: rxPackets,
            tx_packets: txPackets
        )
    }
    return nil
}

func readInterfaceTraffic(_ interfaceName: String) -> InterfaceTraffic? {
    let netstat = Process()
    let output = Pipe()
    netstat.executableURL = URL(fileURLWithPath: "/usr/sbin/netstat")
    netstat.arguments = ["-ibn", "-I", interfaceName]
    netstat.standardOutput = output
    netstat.standardError = FileHandle.nullDevice
    do {
        try netstat.run()
    } catch {
        return nil
    }
    let data = output.fileHandleForReading.readDataToEndOfFile()
    netstat.waitUntilExit()
    guard netstat.terminationStatus == 0, let text = String(data: data, encoding: .utf8) else {
        return nil
    }
    return parseInterfaceTraffic(text, interfaceName: interfaceName, sampledAt: Date().timeIntervalSince1970)
}

func readHostThermalState() -> String {
    switch ProcessInfo.processInfo.thermalState {
    case .nominal: return "nominal"
    case .fair: return "fair"
    case .serious: return "serious"
    case .critical: return "critical"
    @unknown default: return "unknown"
    }
}

func readStatus(includeCapabilities: Bool, includeTraffic: Bool, includeThermal: Bool) -> WiFiStatus {
    let timestamp = Date().timeIntervalSince1970
    let hostThermalState = includeThermal ? readHostThermalState() : nil
    let interfaceName = wifi.interfaceName
    let channel = wifi.wlanChannel()
    let rssi = wifi.rssiValue()
    let noise = wifi.noiseMeasurement()
    let rate = wifi.transmitRate()
    let power = wifi.transmitPower()
    let channels = includeCapabilities ? wifi.supportedWLANChannels().map(channelsByBandAndWidth) : nil
    let apiInterfaces = includeCapabilities ? (client.interfaces() ?? []).compactMap { $0.interfaceName }.sorted() : nil
    return WiFiStatus(
        interface: interfaceName,
        api_visible_interfaces: apiInterfaces,
        interface_mode: modeNames[wifi.interfaceMode()] ?? "unknown",
        radio_power_on: wifi.powerOn(),
        phy_mode: phyNames[wifi.activePHYMode()] ?? "unknown",
        band: channel.flatMap { bandNames[$0.channelBand] },
        channel: channel?.channelNumber,
        channel_width_mhz: channel.flatMap { channelWidths[$0.channelWidth] },
        rssi_dbm: rssi < 0 ? rssi : nil,
        noise_dbm: noise < 0 ? noise : nil,
        tx_rate_mbps: rate.isFinite && rate > 0 ? rate : nil,
        corewlan_transmit_power: power > 0 ? power : nil,
        sampled_at_unix_seconds: timestamp,
        host_thermal_state: hostThermalState,
        interface_traffic: includeTraffic ? interfaceName.flatMap(readInterfaceTraffic) : nil,
        reported_channel_widths_mhz_by_band: channels?.mapValues { $0.keys.sorted() },
        reported_channel_numbers_by_band_and_width_mhz: channels
    )
}

let encoder = JSONEncoder()
let options = CommandLine.arguments.dropFirst()
let includeTraffic = options.contains("--traffic")
let includeThermal = options.contains("--thermal")
let args = options.filter { $0 != "--traffic" && $0 != "--thermal" }
if args.isEmpty {
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    let status = readStatus(includeCapabilities: true, includeTraffic: includeTraffic, includeThermal: includeThermal)
    print(String(decoding: try encoder.encode(status), as: UTF8.self))
} else if args.count == 3, args[0] == "--sample",
          let count = Int(args[1]), count > 0,
          let interval = TimeInterval(args[2]), interval.isFinite, interval > 0 {
    encoder.outputFormatting = [.sortedKeys]
    for index in 0..<count {
        if index > 0 {
            Thread.sleep(forTimeInterval: interval)
        }
        let status = readStatus(includeCapabilities: false, includeTraffic: includeTraffic, includeThermal: includeThermal)
        print(String(decoding: try encoder.encode(status), as: UTF8.self))
    }
} else {
    let usage = "Usage: swift tools/read_wifi_status.swift [--sample COUNT INTERVAL_SECONDS] [--traffic] [--thermal]\n"
    FileHandle.standardError.write(Data(usage.utf8))
    exit(2)
}
