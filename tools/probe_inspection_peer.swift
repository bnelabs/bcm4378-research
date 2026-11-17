import CryptoKit
import Darwin
import Dispatch
import Foundation
import Network
import os
import Security

private let serviceType = "_bcm-inspection._tcp"
private let eventQueue = DispatchQueue(label: "bcm4378.inspection.network")
private let cipher = tls_ciphersuite_t(rawValue: UInt16(TLS_PSK_WITH_AES_128_GCM_SHA256))!
private let previewIntervalMs = 100
private let previewDeadlineMs = 160.0
private let archiveIntervalMs = 16
private let loopback = NWEndpoint.Host("127.0.0.1")
private let completionMarker = Data([0])

private struct ProbeFailure: Error, CustomStringConvertible {
    let description: String
    init(_ description: String) { self.description = description }
}

// The callbacks resolve a single value. The caller waits on a different queue.
private final class Completion<Value: Sendable>: Sendable {
    private let result = OSAllocatedUnfairLock(initialState: Optional<Result<Value, Error>>.none)
    private let ready = DispatchSemaphore(value: 0)

    func resolve(_ outcome: Result<Value, Error>) {
        result.withLock {
            guard $0 == nil else { return }
            $0 = outcome
            ready.signal()
        }
    }

    func wait(_ operation: String, seconds: Int = 5) throws -> Value {
        guard ready.wait(timeout: .now() + .seconds(seconds)) == .success,
              let outcome = result.withLock({ $0 })
        else { throw ProbeFailure("Timed out while \(operation)") }
        return try outcome.get()
    }
}

private func serviceName(for key: Data) -> String {
    let label = SHA256.hash(data: key).prefix(8).map { String(format: "%02x", $0) }.joined()
    return "inspection-\(label)"
}

private func parameters(key: Data, includePeer: Bool,
                        serviceClass: NWParameters.ServiceClass = .bestEffort) -> NWParameters {
    let tls = NWProtocolTLS.Options()
    let options = tls.securityProtocolOptions
    sec_protocol_options_set_min_tls_protocol_version(options, .TLSv12)
    sec_protocol_options_set_max_tls_protocol_version(options, .TLSv12)
    sec_protocol_options_append_tls_ciphersuite(options, cipher)
    let secret = key.withUnsafeBytes { DispatchData(bytes: $0) }
    let identity = Data("bcm4378-inspection-v1".utf8).withUnsafeBytes { DispatchData(bytes: $0) }
    sec_protocol_options_add_pre_shared_key(options, secret as __DispatchData, identity as __DispatchData)
    let tcp = NWProtocolTCP.Options()
    tcp.noDelay = true
    let parameters = NWParameters(tls: tls, tcp: tcp)
    parameters.includePeerToPeer = includePeer
    parameters.serviceClass = serviceClass
    return parameters
}

private enum Stream: UInt8, Sendable {
    case preview = 1
    case archive = 2

    var count: Int { self == .preview ? 20 : 256 }
    var bytes: Int { self == .preview ? 2_048 : 4_096 }
    var serviceClass: NWParameters.ServiceClass { self == .preview ? .interactiveVideo : .background }

    func payload(_ sequence: Int) -> Data {
        var data = Data(repeating: rawValue, count: bytes)
        data[1] = UInt8(sequence)
        data[2] = ~data[1]
        return data
    }
}

private enum Mode: String, Encodable {
    case loopback, lan, split

    var includesPeer: Bool { self == .split }
}

private func start(_ connection: NWConnection) -> Completion<Void> {
    let ready = Completion<Void>()
    connection.stateUpdateHandler = { state in
        switch state {
        case .ready: ready.resolve(.success(()))
        case .failed(let error): ready.resolve(.failure(error))
        case .waiting(.tls(let status)): ready.resolve(.failure(NWError.tls(status)))
        case .cancelled: ready.resolve(.failure(ProbeFailure("Connection cancelled")))
        default: break
        }
    }
    connection.start(queue: eventQueue)
    return ready
}

private func verifyTLS(_ connection: NWConnection) throws {
    guard let metadata = connection.metadata(definition: NWProtocolTLS.definition) as? NWProtocolTLS.Metadata,
          sec_protocol_metadata_get_negotiated_tls_ciphersuite(metadata.securityProtocolMetadata) == cipher,
          sec_protocol_metadata_get_negotiated_tls_protocol_version(metadata.securityProtocolMetadata) == .TLSv12
    else { throw ProbeFailure("Expected the paired TLS session") }
}

private func send(_ data: Data, on connection: NWConnection) throws {
    let done = Completion<Void>()
    connection.send(content: data, completion: .contentProcessed { error in
        done.resolve(error.map { .failure($0) } ?? .success(()))
    })
    try done.wait("sending")
}

private func read(_ count: Int, from connection: NWConnection, seconds: Int = 5) throws -> Data {
    let done = Completion<Data>()
    connection.receive(minimumIncompleteLength: count, maximumLength: count) { data, _, _, error in
        if let error {
            done.resolve(.failure(error))
        } else if let data, data.count == count {
            done.resolve(.success(data))
        } else {
            done.resolve(.failure(ProbeFailure("Stream ended before \(count) bytes arrived")))
        }
    }
    return try done.wait("receiving", seconds: seconds)
}

private func receiveWorkload(_ connection: NWConnection) throws {
    try start(connection).wait("setting up receiver TLS", seconds: 12)
    try verifyTLS(connection)
    let header = try read(1, from: connection, seconds: 15)
    guard let stream = Stream(rawValue: header[header.startIndex]) else {
        throw ProbeFailure("Unknown stream kind")
    }
    for sequence in 0..<stream.count {
        let data = try read(stream.bytes, from: connection)
        guard data == stream.payload(sequence) else { throw ProbeFailure("Receiver payload check failed") }
        if stream == .preview {
            try send(Data(data.prefix(3)), on: connection)
        }
    }
    if stream == .archive {
        try send(Data([Stream.archive.rawValue]), on: connection)
    }
    // Keep the receiver open until the client has read the last acknowledgement.
    guard try read(1, from: connection) == completionMarker else {
        throw ProbeFailure("Unexpected completion marker")
    }
}

private func listener(key: Data, loopbackOnly: Bool) throws -> NWListener {
    let params = parameters(key: key, includePeer: !loopbackOnly)
    if loopbackOnly {
        params.requiredLocalEndpoint = .hostPort(host: loopback, port: .any)
        params.requiredInterfaceType = .loopback
    }
    let listener = try NWListener(using: params)
    listener.newConnectionLimit = 8
    listener.service = .init(name: serviceName(for: key), type: serviceType)
    listener.newConnectionHandler = { connection in
        DispatchQueue.global().async {
            defer { connection.cancel() }
            // A client can finish only after it gets the acknowledgement for its verified data.
            try? receiveWorkload(connection)
        }
    }
    let ready = Completion<Void>()
    listener.stateUpdateHandler = { state in
        switch state {
        case .ready: ready.resolve(.success(()))
        case .failed(let error): ready.resolve(.failure(error))
        case .cancelled: ready.resolve(.failure(ProbeFailure("Listener cancelled")))
        default: break
        }
    }
    listener.start(queue: eventQueue)
    do {
        try ready.wait("starting listener")
    } catch {
        listener.cancel()
        throw error
    }
    return listener
}

private struct Discovered: Sendable {
    let endpoint: NWEndpoint
    let interface: NWInterface
}

private func discover(key: Data, interfaces: Set<String>, mode: Mode) throws -> [String: Discovered] {
    let params = NWParameters()
    params.includePeerToPeer = mode.includesPeer
    if mode == .loopback { params.requiredInterfaceType = .loopback }
    let browser = NWBrowser(for: .bonjour(type: serviceType, domain: "local."), using: params)
    let found = Completion<[String: Discovered]>()
    let name = serviceName(for: key)
    browser.browseResultsChangedHandler = { results, _ in
        var matches: [String: Discovered] = [:]
        for result in results {
            guard case .service(let instance, let type, let domain, _) = result.endpoint,
                  instance == name else { continue }
            for interface in result.interfaces where interfaces.contains(interface.name) {
                matches[interface.name] = Discovered(
                    endpoint: .service(name: instance, type: type, domain: domain, interface: interface),
                    interface: interface
                )
            }
        }
        if interfaces.isSubset(of: Set(matches.keys)) {
            found.resolve(.success(matches))
        }
    }
    browser.stateUpdateHandler = { state in
        if case .failed(let error) = state { found.resolve(.failure(error)) }
    }
    browser.start(queue: eventQueue)
    defer { browser.cancel() }
    return try found.wait("discovering the paired service on \(interfaces.sorted().joined(separator: ", "))", seconds: 12)
}

private struct PathSample: Encodable {
    let interface: String
    let radio: String?
    let sent_application_bytes: UInt64
    let received_application_bytes: UInt64
    let sent_ip_packets: UInt64
    let received_ip_packets: UInt64
    let retransmitted_transport_bytes: UInt64

    init(_ report: NWConnection.DataTransferReport.PathReport) {
        interface = report.interface.name
        radio = report.radioType.map { String(describing: $0) }
        sent_application_bytes = report.sentApplicationByteCount
        received_application_bytes = report.receivedApplicationByteCount
        sent_ip_packets = report.sentIPPacketCount
        received_ip_packets = report.receivedIPPacketCount
        retransmitted_transport_bytes = report.retransmittedTransportByteCount
    }
}

private func paths(_ pending: NWConnection.PendingDataTransferReport, on required: String,
                   payloadBytes: Int) throws -> [PathSample] {
    let reports = Completion<[PathSample]>()
    pending.collect(queue: eventQueue) { report in
        reports.resolve(.success(report.pathReports.map(PathSample.init)))
    }
    let active = try reports.wait("collecting the path report").filter {
        $0.sent_application_bytes > 0 || $0.received_application_bytes > 0
    }
    let sentBytes = active.reduce(0) { $0 + $1.sent_application_bytes }
    guard sentBytes >= UInt64(payloadBytes), active.allSatisfy({ $0.interface == required }) else {
        throw ProbeFailure("Expected \(payloadBytes) payload bytes on \(required). Reported \(sentBytes) bytes on \(active.map(\.interface))")
    }
    return active
}

private func elapsedMs(from start: DispatchTime) -> Double {
    (Double(DispatchTime.now().uptimeNanoseconds) - Double(start.uptimeNanoseconds)) / 1_000_000
}

private func waitUntil(_ time: DispatchTime) {
    let now = DispatchTime.now().uptimeNanoseconds
    if now < time.uptimeNanoseconds {
        Thread.sleep(forTimeInterval: Double(time.uptimeNanoseconds - now) / 1_000_000_000)
    }
}

private struct PreviewResult: Encodable, Sendable {
    let offered: Int
    let acknowledged_by_deadline: Int
    let payload_bytes_verified: Int
    let started_ms: Double
    let finished_ms: Double
    let round_trip_median_ms: Double
    let round_trip_p95_ms: Double
    let release_to_ack_ms: [Double]
    let paths: [PathSample]
}

private func runPreviews(_ connection: NWConnection, on required: String, origin: DispatchTime) throws -> PreviewResult {
    let pending = connection.startDataTransferReport()
    let stream = Stream.preview
    let started = elapsedMs(from: origin)
    try send(Data([stream.rawValue]), on: connection)
    var roundTrips: [Double] = []
    var fromRelease: [Double] = []
    for sequence in 0..<stream.count {
        let release = origin + .milliseconds(sequence * previewIntervalMs)
        waitUntil(release)
        let data = stream.payload(sequence)
        let sent = DispatchTime.now()
        try send(data, on: connection)
        guard try read(3, from: connection) == data.prefix(3) else {
            throw ProbeFailure("Unexpected preview acknowledgement")
        }
        roundTrips.append(elapsedMs(from: sent))
        fromRelease.append(elapsedMs(from: release))
    }
    let finished = elapsedMs(from: origin)
    try send(completionMarker, on: connection)
    let ordered = roundTrips.sorted()
    let verifiedBytes = stream.count * stream.bytes
    return PreviewResult(
        offered: stream.count,
        acknowledged_by_deadline: fromRelease.filter { $0 <= previewDeadlineMs }.count,
        payload_bytes_verified: verifiedBytes,
        started_ms: started, finished_ms: finished,
        round_trip_median_ms: (ordered[ordered.count / 2 - 1] + ordered[ordered.count / 2]) / 2,
        round_trip_p95_ms: ordered[Int(ceil(Double(ordered.count) * 0.95)) - 1],
        release_to_ack_ms: fromRelease,
        paths: try paths(pending, on: required, payloadBytes: verifiedBytes)
    )
}

private struct ArchiveResult: Encodable, Sendable {
    let payload_bytes_verified: Int
    let started_ms: Double
    let finished_ms: Double
    let paths: [PathSample]
}

private func runArchive(_ connection: NWConnection, on required: String, origin: DispatchTime) throws -> ArchiveResult {
    let pending = connection.startDataTransferReport()
    let stream = Stream.archive
    let started = elapsedMs(from: origin)
    try send(Data([stream.rawValue]), on: connection)
    for sequence in 0..<stream.count {
        let next = DispatchTime.now() + .milliseconds(archiveIntervalMs)
        try send(stream.payload(sequence), on: connection)
        waitUntil(next)
    }
    guard try read(1, from: connection) == Data([stream.rawValue]) else {
        throw ProbeFailure("Unexpected archive acknowledgement")
    }
    let finished = elapsedMs(from: origin)
    try send(completionMarker, on: connection)
    let verifiedBytes = stream.count * stream.bytes
    return ArchiveResult(
        payload_bytes_verified: verifiedBytes,
        started_ms: started, finished_ms: finished,
        paths: try paths(pending, on: required, payloadBytes: verifiedBytes)
    )
}

private struct Workload: Encodable {
    let mode: Mode
    let preview_service_class = "interactiveVideo"
    let archive_service_class = "background"
    let preview_interval_ms = previewIntervalMs
    let preview_deadline_ms = previewDeadlineMs
    let archive_chunk_interval_ms = archiveIntervalMs
    let tls_cipher = "TLS_PSK_WITH_AES_128_GCM_SHA256"
    let mismatched_key_tls_status: Int32?
    let preview: PreviewResult
    let archive: ArchiveResult
}

private func exercise(preview: NWConnection, previewInterface: String,
                      archive: NWConnection, archiveInterface: String,
                      mode: Mode, wrongKeyStatus: Int32?) throws -> Workload {
    defer {
        preview.cancel()
        archive.cancel()
    }
    let previewReady = start(preview)
    let archiveReady = start(archive)
    try previewReady.wait("opening preview connection", seconds: 12)
    try archiveReady.wait("opening archive connection", seconds: 12)
    try verifyTLS(preview)
    try verifyTLS(archive)

    let origin = DispatchTime.now()
    let archiveDone = Completion<ArchiveResult>()
    DispatchQueue.global().async {
        archiveDone.resolve(Result { try runArchive(archive, on: archiveInterface, origin: origin) })
    }
    let previewResult = try runPreviews(preview, on: previewInterface, origin: origin)
    let archiveResult = try archiveDone.wait("completing archive", seconds: 20)
    return Workload(mode: mode, mismatched_key_tls_status: wrongKeyStatus,
                    preview: previewResult, archive: archiveResult)
}

private func selftest() throws -> Workload {
    var key = Data(count: 32)
    let status = key.withUnsafeMutableBytes { buffer in
        SecRandomCopyBytes(kSecRandomDefault, buffer.count, buffer.baseAddress!)
    }
    guard status == errSecSuccess else { throw ProbeFailure("Could not generate a local test key") }
    let server = try listener(key: key, loopbackOnly: true)
    defer { server.cancel() }
    guard let port = server.port else { throw ProbeFailure("Listener has no port") }
    let endpoint = NWEndpoint.hostPort(host: loopback, port: port)
    var wrongKey = key
    wrongKey[0] ^= 1
    let denied = NWConnection(to: endpoint, using: parameters(key: wrongKey, includePeer: false))
    defer { denied.cancel() }
    let rejection: Int32
    do {
        try start(denied).wait("testing a mismatched key")
        throw ProbeFailure("A mismatched key was accepted")
    } catch NWError.tls(let status) {
        rejection = status
    }
    denied.cancel()
    return try run(key: key, mode: .loopback, infrastructure: "lo0", wrongKeyStatus: rejection)
}

private func run(key: Data, mode: Mode, infrastructure: String, wrongKeyStatus: Int32? = nil) throws -> Workload {
    let previewName = mode.includesPeer ? "awdl0" : infrastructure
    let matches = try discover(key: key, interfaces: [previewName, infrastructure], mode: mode)
    guard let preview = matches[previewName], let archive = matches[infrastructure] else {
        throw ProbeFailure("The paired listener did not advertise on the required interfaces")
    }
    let previewParams = parameters(key: key, includePeer: mode.includesPeer, serviceClass: Stream.preview.serviceClass)
    let archiveParams = parameters(key: key, includePeer: false, serviceClass: Stream.archive.serviceClass)
    previewParams.requiredInterface = preview.interface
    archiveParams.requiredInterface = archive.interface
    return try exercise(preview: NWConnection(to: preview.endpoint, using: previewParams), previewInterface: previewName,
                        archive: NWConnection(to: archive.endpoint, using: archiveParams),
                        archiveInterface: infrastructure, mode: mode, wrongKeyStatus: wrongKeyStatus)
}

private func readKey(_ path: String) throws -> Data {
    let key = try Data(contentsOf: URL(fileURLWithPath: path))
    guard key.count == 32 else { throw ProbeFailure("Expected a file containing a fresh 32-byte pairing key") }
    return key
}

private func printResult(_ result: Workload) throws {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    print(String(decoding: try encoder.encode(result), as: UTF8.self))
}

let arguments = Array(CommandLine.arguments.dropFirst())
do {
    switch arguments.first {
    case "selftest" where arguments.count == 1:
        try printResult(selftest())
    case "serve" where arguments.count == 2:
        let key = try readKey(arguments[1])
        let server = try listener(key: key, loopbackOnly: false)
        FileHandle.standardOutput.write(Data("Paired inspection listener ready for 90 seconds.\n".utf8))
        Thread.sleep(forTimeInterval: 90)
        server.cancel()
    case "run" where (3...4).contains(arguments.count):
        guard let mode = Mode(rawValue: arguments[2]), mode != .loopback else {
            throw ProbeFailure("Expected lan or split")
        }
        let infrastructure = arguments.count == 4 ? arguments[3] : "en0"
        guard infrastructure != "awdl0", infrastructure != "lo0", if_nametoindex(infrastructure) > 0 else {
            throw ProbeFailure("Expected an existing infrastructure interface")
        }
        let key = try readKey(arguments[1])
        try printResult(run(key: key, mode: mode, infrastructure: infrastructure))
    default:
        throw ProbeFailure("Usage: probe_inspection_peer selftest | serve KEYFILE | run KEYFILE lan|split [LAN_INTERFACE]")
    }
} catch {
    FileHandle.standardError.write(Data("\(error)\n".utf8))
    exit(1)
}
