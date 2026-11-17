import Foundation

enum Band: String, Codable, CaseIterable, Identifiable, Sendable {
    case two = "2.4 GHz"
    case five = "5 GHz"
    case six = "6 GHz"

    var id: Self { self }

    func frequency(_ channel: Int) -> Int {
        switch self {
        case .two: return channel == 14 ? 2484 : 2407 + 5 * channel
        case .five: return 5000 + 5 * channel
        case .six: return channel == 2 ? 5935 : 5950 + 5 * channel
        }
    }
}

struct RadioChannel: Codable, Identifiable, Hashable, Sendable {
    let band: Band
    let number: Int
    let width: Int

    var id: String { "\(band.rawValue)-\(number)-\(width)" }
    var label: String { "\(band.rawValue) · Channel \(number) · \(width) MHz" }
}

struct LinkStatus: Codable, Sendable {
    let measuredAt: Date
    let interface: String?
    let mode: String
    let powerOn: Bool
    let channel: RadioChannel?
    let rssi: Int?
    let noise: Int?
    let rate: Double?
    let osPowerValue: Int?
    let phy: String?
    let country: String?
    let routes: [String]
    let channels: [RadioChannel]
    let canChangeRadio: Bool
    let radioControlReason: String

    var snr: Int? {
        guard let rssi, let noise else { return nil }
        return rssi - noise
    }
}

struct HardwareIdentity: Codable, Sendable {
    let model: String
    let systemVersion: String
    let chip: String?
    let chipRevision: String?
    let pciID: String?
    let board: String?
    let firmware: String?
    let firmwareID: String?
    let firmwarePath: String?
    let resolvedFirmwarePath: String?
    let firmwareDigest: String?
    let threadX: String?
    let regulatoryPath: String?
    let boardSettingsPath: String?
    let powerCapsPath: String?
    let capabilities: [String]
    let roles: [InterfaceRole]
}

struct InterfaceRole: Codable, Identifiable, Sendable {
    let name: String
    let role: String
    var id: String { name }
}

struct RadioReport: Decodable, Identifiable, Sendable {
    let group: String
    let subgroup: String
    let name: String
    let format: Int
    let value: Int64?

    var id: String { "\(group)/\(subgroup)/\(name)" }

    var switchTime: Bool {
        format == 3 && (name == "Dwell Time" || name == "Phy Switch Time")
    }

}

struct ReportSample: Decodable, Sendable {
    let sampledAtUnixSeconds: Double
    let reports: [RadioReport]

    var measuredAt: Date { Date(timeIntervalSince1970: sampledAtUnixSeconds) }

    func value(_ group: String, _ subgroup: String, _ name: String) -> Int64? {
        reports.first { $0.group == group && $0.subgroup == subgroup && $0.name == name }?.value
    }

    func airtimePercent(_ name: String) -> Int? {
        guard let row = reports.first(where: {
            $0.group == "Interface en0" && $0.name.trimmingCharacters(in: .whitespaces) == name
        }), let value = row.value, (0...100).contains(value) else { return nil }
        return Int(value)
    }
}

struct RadioReading: Sendable {
    let status: LinkStatus
    let airtime: ReportSample?
    let channels: ReportSample?
    let rawChannels: Data?
    let reportNotice: String?
}

struct RegionPlan: Decodable, Sendable {
    let fileSha256: String
    let locales: Locales

    struct Locales: Decodable, Sendable {
        let commonCentersByBandAndWidthMhz: [String: [String: [Int]]]
        let regions: [String: Region]
    }

    struct Region: Decodable, Sendable {
        let bands: [String: RegionBand]
    }

    struct RegionBand: Decodable, Sendable {
        let channelBlocksByWidthMhz: [String: ChannelList]
    }

    struct ChannelList: Decodable, Sendable {
        let centers: [Int]
        let primaries: [Int]
    }
}

struct TimingComparison: Decodable, Sendable {
    let elapsedSeconds: Double?
    let budgetMs: String?
    let unpairedHistograms: [String]
    let reports: [TimingResult]

    struct TimingResult: Decodable, Identifiable, Sendable {
        let group: String
        let report: String
        let unit: String
        let events: Int
        let mean: Double?
        let percentileRanges: [String: [Int64]?]
        let overBudgetCountRange: [Int]?

        var id: String { "\(group)/\(report)" }
        var p95: [Int64]? { percentileRanges["p95"] ?? nil }
    }
}

struct ThreadXAdvisories: Decodable, Sendable {
    let checkedOn: String
    let source: URL
    let rows: [Advisory]

    struct Advisory: Decodable, Identifiable, Sendable {
        let cve: String
        let component: String
        let severity: String
        let impact: String
        let affected: String
        let fixed: String?
        let url: URL
        var id: String { cve }
    }
}

enum AppData {
    static func decode<T: Decodable>(_ type: T.Type, _ data: Data) throws -> T {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(type, from: data)
    }
}
