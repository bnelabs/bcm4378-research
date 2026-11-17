import Darwin
import Foundation
import Security

enum ServiceClass: String, CaseIterable, Identifiable, Sendable {
    case bestEffort = "Best effort"
    case background = "Background"
    case signaling = "Signaling"
    case video = "Interactive video"
    case voice = "Interactive voice"
    case responsiveMedia = "Responsive media"
    case streaming = "Media streaming"
    case management = "Network management"
    case responsiveData = "Responsive data"

    var id: Self { self }
    var value: Int32 {
        switch self {
        case .bestEffort: return NET_SERVICE_TYPE_BE
        case .background: return NET_SERVICE_TYPE_BK
        case .signaling: return NET_SERVICE_TYPE_SIG
        case .video: return NET_SERVICE_TYPE_VI
        case .voice: return NET_SERVICE_TYPE_VO
        case .responsiveMedia: return NET_SERVICE_TYPE_RV
        case .streaming: return NET_SERVICE_TYPE_AV
        case .management: return NET_SERVICE_TYPE_OAM
        case .responsiveData: return NET_SERVICE_TYPE_RD
        }
    }

    var effect: String {
        switch self {
        case .bestEffort: return "Use the normal queue for ordinary traffic."
        case .background: return "Let more time-sensitive traffic go first. A busy link may deliver an upload more slowly."
        case .signaling: return "Request the class for short messages that set up or coordinate a connection."
        case .video: return "Ask macOS for a queue suited to video calls. The network can still delay or drop traffic."
        case .voice: return "Ask macOS for the most delay-sensitive queue. Use it for small, time-critical streams."
        case .responsiveMedia: return "Request the class for audio or video that should respond quickly."
        case .streaming: return "Request the class for sustained audio or video playback."
        case .management: return "Request the class for network administration or status traffic."
        case .responsiveData: return "Request the class for data where a user is waiting for a response."
        }
    }
}

struct SocketResult: Sendable {
    let service: Int32
    let bytesPerSecond: UInt64
}

struct TransferResult: Decodable, Sendable {
    let mode: String
    let mismatchedKeyTlsStatus: Int?
    let preview: Preview
    let archive: Archive
    let previewsAcknowledgedBetweenArchiveAttempts: Int?

    struct Preview: Decodable, Sendable {
        let offered: Int
        let acknowledgedByDeadline: Int
        let roundTripP95Ms: Double
        let paths: [Path]
    }

    struct Archive: Decodable, Sendable {
        let payloadBytesVerified: Int
        let paths: [Path]
        let attempts: [Attempt]?
    }

    struct Attempt: Decodable, Sendable {
        let receiverNextChunk: Int?
        let paths: [Path]
    }

    struct Path: Decodable, Sendable {
        let interface: String
    }
}

enum TransferMode: String, CaseIterable, Identifiable, Sendable {
    case lan, split
    var id: Self { self }
    var label: String { self == .lan ? "Both streams on Wi-Fi" : "Direct preview + Wi-Fi archive" }
}

enum Inspection: String, CaseIterable, Identifiable, Sendable {
    case firmware = "Firmware layout"
    case microcode = "Radio microcode"
    case board = "Board and radio profiles"
    case ranging = "Saved distance result"
    case sleep = "Saved sleep and wake log"
    case keepalive = "Saved keepalive status"
    case savedRAM = "Saved ThreadX memory capture"

    var id: Self { self }
    var effect: String {
        switch self {
        case .firmware: return "Read the installed image’s version markers and component layout."
        case .microcode: return "Identify the two programs that control the radio cores and the bands assigned to them."
        case .board: return "Read calibration, country rules and power limits from the files selected for this board."
        case .ranging: return "Read average distance and measurement counts from a saved timing result."
        case .sleep: return "Group wake events from a saved macOS power log by the reported reason."
        case .keepalive: return "Read status from a saved driver record. See whether a TCP session missed replies or requested a wake."
        case .savedRAM: return "Read the thread list from a saved driver capture that matches the installed firmware."
        }
    }

    var needsFile: Bool {
        switch self {
        case .ranging, .sleep, .keepalive, .savedRAM: return true
        default: return false
        }
    }
}

struct CaptureLayout: Sendable {
    var total: String = "1892352"
    var retained: String = "0"
    var prefix: String = "0"
}

enum Workflows {
    static func regionPlan(path: String, first: String, second: String) throws -> RegionPlan {
        let codes = Array(Set([first, second])).sorted()
        guard codes.allSatisfy({ code in
            code.utf8.count == 2 && code.utf8.allSatisfy { (65...90).contains($0) || (48...57).contains($0) }
        }) else {
            throw KYWError("Enter two-character country codes such as TR, US or JP.")
        }
        let args = codes.flatMap { ["--locale", $0] } + [path]
        let plans = try AppData.decode([RegionPlan].self, Resources.python("audit_clm_channels.py", args))
        guard let plan = plans.first, Set(plan.locales.regions.keys) == Set(codes) else {
            throw KYWError("The installed country table did not return a plan for both codes.")
        }
        return plan
    }

    static func compareTiming(before: Data, after: Data, budget: String) throws -> TimingComparison {
        guard let milliseconds = Double(budget), milliseconds.isFinite, milliseconds >= 0 else {
            throw KYWError("Enter a nonnegative delay in milliseconds.")
        }
        let directory = try ToolRunner.temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let start = directory.appendingPathComponent("before.json")
        let stop = directory.appendingPathComponent("after.json")
        try before.write(to: start)
        try after.write(to: stop)
        let result = try Resources.python("summarize_switch_timing.py",
            [stop.path, "--before", start.path, "--budget-ms", budget])
        return try AppData.decode(TimingComparison.self, result)
    }

    static func checkSocket(service: ServiceClass, pace: UInt64) throws -> SocketResult {
        let file = socket(AF_INET, SOCK_STREAM, 0)
        guard file >= 0 else { throw socketError("Open test socket") }
        defer { close(file) }

        var serviceValue = service.value
        var serviceSize = socklen_t(MemoryLayout.size(ofValue: serviceValue))
        var paceValue = pace
        var paceSize = socklen_t(MemoryLayout.size(ofValue: paceValue))
        guard setsockopt(file, SOL_SOCKET, SO_NET_SERVICE_TYPE, &serviceValue, serviceSize) == 0 else {
            throw socketError("Set priority")
        }
        guard setsockopt(file, SOL_SOCKET, SO_MAX_PACING_RATE, &paceValue, paceSize) == 0 else {
            throw socketError("Set pacing")
        }
        guard getsockopt(file, SOL_SOCKET, SO_NET_SERVICE_TYPE, &serviceValue, &serviceSize) == 0,
              getsockopt(file, SOL_SOCKET, SO_MAX_PACING_RATE, &paceValue, &paceSize) == 0 else {
            throw socketError("Read socket settings")
        }
        guard serviceSize == MemoryLayout<Int32>.size, paceSize == MemoryLayout<UInt64>.size else {
            throw KYWError("macOS returned unexpected socket option sizes.")
        }
        return SocketResult(service: serviceValue, bytesPerSecond: paceValue)
    }

    private static func socketError(_ action: String) -> KYWError {
        KYWError("\(action) failed. \(String(cString: strerror(errno)))")
    }

    static func transfer(recovery: Bool, peer: URL? = nil, mode: TransferMode = .lan, interface: String = "en0") throws -> TransferResult {
        let args = peer.map { [recovery ? "run-resume" : "run", $0.path, mode.rawValue, interface] }
            ?? [recovery ? "selftest-resume" : "selftest"]
        let data = try ToolRunner.run(Resources.helper("probe_inspection_peer"), args, timeout: 85)
        return try AppData.decode(TransferResult.self, data)
    }

    static func listen(key: URL) throws {
        _ = try ToolRunner.run(Resources.helper("probe_inspection_peer"), ["serve", key.path], timeout: 100)
    }

    static func makeKey(at destination: URL) throws {
        var bytes = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else {
            throw KYWError("macOS could not generate a pairing key.")
        }
        let directory = try ToolRunner.temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let staged = directory.appendingPathComponent("pairing.key")
        try Data(bytes).write(to: staged)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: staged.path)
        try FileManager.default.moveItem(at: staged, to: destination)
    }

    static func inspect(_ selection: Inspection, identity: HardwareIdentity?, file: URL?, layout: CaptureLayout) throws -> String {
        func require(_ path: String?, _ purpose: String) throws -> String {
            guard let path else { throw KYWError("KYW could not find \(purpose).") }
            return path
        }
        let script: String
        let args: [String]
        switch selection {
        case .firmware:
            script = "inspect_firmware.py"
            args = [try require(identity?.firmwarePath, "the installed firmware"), "--embedded-metadata"]
        case .microcode:
            script = "inspect_d11_microcode.py"
            args = [try require(identity?.firmwarePath, "the installed firmware"),
                    "--board-profile", try require(identity?.boardSettingsPath, "the installed board profile")]
        case .board:
            script = "inspect_radio_sidecars.py"
            let inputs = [("--nvram", identity?.boardSettingsPath), ("--clm", identity?.regulatoryPath),
                          ("--txcap", identity?.powerCapsPath)].compactMap { flag, path in path.map { [flag, $0] } }
            guard !inputs.isEmpty else { throw KYWError("KYW could not find any board files.") }
            args = inputs.flatMap { $0 }
        case .ranging:
            script = "inspect_ranging_result.py"
            args = [try require(file?.path, "the saved distance result")]
        case .sleep:
            script = "inspect_sleep_wake.py"
            args = ["--pmset-log", try require(file?.path, "the saved macOS power log")]
        case .keepalive:
            script = "inspect_sleep_wake.py"
            args = ["--tko-status", try require(file?.path, "the saved keepalive status")]
        case .savedRAM:
            script = "compare_ram_capture.py"
            args = [try require(file?.path, "the saved memory capture"),
                    try require(identity?.firmwarePath, "the installed firmware"),
                    "--ram-bytes", layout.total, "--save-restore-bytes", layout.retained,
                    "--prefix-bytes", layout.prefix, "--threadx-list"]
        }
        return String(decoding: try Resources.python(script, args), as: UTF8.self)
    }

    static func advisories() throws -> ThreadXAdvisories {
        try AppData.decode(ThreadXAdvisories.self, Data(contentsOf: Resources.folder.appendingPathComponent("threadx-advisories.json")))
    }
}
