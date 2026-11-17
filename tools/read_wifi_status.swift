import CoreWLAN
import Foundation

guard let wifi = CWWiFiClient.shared().interface() else {
    FileHandle.standardError.write(Data("CoreWLAN found no Wi-Fi interface.\n".utf8))
    exit(1)
}

struct WiFiStatus: Encodable {
    let interface: String?
    let phy_mode: String
    let channel: Int?
    let channel_width_mhz: Int?
    let rssi_dbm: Int?
    let noise_dbm: Int?
    let tx_rate_mbps: Double?
}

let phyNames: [CWPHYMode: String] = [
    .mode11a: "802.11a", .mode11b: "802.11b", .mode11g: "802.11g",
    .mode11n: "802.11n", .mode11ac: "802.11ac", .mode11ax: "802.11ax",
    .mode11be: "802.11be",
]
let channelWidths: [CWChannelWidth: Int] = [
    .width20MHz: 20, .width40MHz: 40, .width80MHz: 80, .width160MHz: 160,
]

let channel = wifi.wlanChannel()
let rssi = wifi.rssiValue()
let noise = wifi.noiseMeasurement()
let rate = wifi.transmitRate()
let status = WiFiStatus(
    interface: wifi.interfaceName,
    phy_mode: phyNames[wifi.activePHYMode()] ?? "unknown",
    channel: channel?.channelNumber,
    channel_width_mhz: channel.flatMap { channelWidths[$0.channelWidth] },
    rssi_dbm: rssi < 0 ? rssi : nil,
    noise_dbm: noise < 0 ? noise : nil,
    tx_rate_mbps: rate.isFinite && rate > 0 ? rate : nil
)
let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
print(String(decoding: try encoder.encode(status), as: UTF8.self))
