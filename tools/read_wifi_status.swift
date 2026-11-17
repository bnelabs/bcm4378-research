import CoreWLAN
import Foundation

let client = CWWiFiClient.shared()
guard let wifi = client.interface() else {
    FileHandle.standardError.write(Data("CoreWLAN found no Wi-Fi interface.\n".utf8))
    exit(1)
}

struct WiFiStatus: Encodable {
    let interface: String?
    let api_visible_interfaces: [String]?
    let interface_mode: String
    let phy_mode: String
    let channel: Int?
    let channel_width_mhz: Int?
    let rssi_dbm: Int?
    let noise_dbm: Int?
    let tx_rate_mbps: Double?
    let sampled_at_unix_seconds: Double
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

func readStatus(includeCapabilities: Bool) -> WiFiStatus {
    let timestamp = Date().timeIntervalSince1970
    let channel = wifi.wlanChannel()
    let rssi = wifi.rssiValue()
    let noise = wifi.noiseMeasurement()
    let rate = wifi.transmitRate()
    let channels = includeCapabilities ? wifi.supportedWLANChannels().map(channelsByBandAndWidth) : nil
    let apiInterfaces = includeCapabilities ? (client.interfaces() ?? []).compactMap { $0.interfaceName }.sorted() : nil
    return WiFiStatus(
        interface: wifi.interfaceName,
        api_visible_interfaces: apiInterfaces,
        interface_mode: modeNames[wifi.interfaceMode()] ?? "unknown",
        phy_mode: phyNames[wifi.activePHYMode()] ?? "unknown",
        channel: channel?.channelNumber,
        channel_width_mhz: channel.flatMap { channelWidths[$0.channelWidth] },
        rssi_dbm: rssi < 0 ? rssi : nil,
        noise_dbm: noise < 0 ? noise : nil,
        tx_rate_mbps: rate.isFinite && rate > 0 ? rate : nil,
        sampled_at_unix_seconds: timestamp,
        reported_channel_widths_mhz_by_band: channels?.mapValues { $0.keys.sorted() },
        reported_channel_numbers_by_band_and_width_mhz: channels
    )
}

let encoder = JSONEncoder()
let args = Array(CommandLine.arguments.dropFirst())
if args.isEmpty {
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    print(String(decoding: try encoder.encode(readStatus(includeCapabilities: true)), as: UTF8.self))
} else if args.count == 3, args[0] == "--sample",
          let count = Int(args[1]), count > 0,
          let interval = TimeInterval(args[2]), interval.isFinite, interval > 0 {
    encoder.outputFormatting = [.sortedKeys]
    for index in 0..<count {
        if index > 0 {
            Thread.sleep(forTimeInterval: interval)
        }
        print(String(decoding: try encoder.encode(readStatus(includeCapabilities: false)), as: UTF8.self))
    }
} else {
    let usage = "Usage: swift tools/read_wifi_status.swift [--sample COUNT INTERVAL_SECONDS]\n"
    FileHandle.standardError.write(Data(usage.utf8))
    exit(2)
}
