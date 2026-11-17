import Foundation

enum SmokeTest {
    static func run() -> Int32 {
        do {
            try require(!SystemRadio.radioPermission(
                interface: "en0", associated: true, routes: ["en7"], wired: ["en7"]
            ).0, "An associated radio must reject a change")
            try require(!SystemRadio.radioPermission(
                interface: "en0", associated: false, routes: ["en0"], wired: ["en7"]
            ).0, "A Wi-Fi default route must reject a change")
            try require(!SystemRadio.radioPermission(
                interface: "en0", associated: false, routes: ["en7", "utun0"], wired: ["en7"]
            ).0, "All default routes must be understood")
            try require(SystemRadio.radioPermission(
                interface: "en0", associated: false, routes: ["en7"], wired: ["en7"]
            ).0, "Detached Wi-Fi with a verified Ethernet default route should qualify")
            let advisories = try Workflows.advisories()
            try require(advisories.rows.count == Set(advisories.rows.map(\.cve)).count && !advisories.rows.isEmpty,
                        "Upstream advisories must have unique CVE IDs")
            print("ThreadX advisory entries: \(advisories.rows.count)")

            let identity = try SystemRadio.identity()
            let radio = SystemRadio.reading()
            print("Live registry: \(identity.chip ?? "unidentified"), firmware \(identity.firmware ?? "unidentified"), \(identity.threadX ?? "unverified RTOS"), \(identity.capabilities.count) feature words")
            print("Default routes: \(radio.status.routes.joined(separator: ", "))")
            print("Reported country: \(radio.status.country ?? "unavailable")")
            print("Associated channel: \(radio.status.channel?.label ?? "none"), available channel entries: \(radio.status.channels.count)")
            if radio.status.carriesInternet {
                try require(!radio.status.canChangeRadio, "Live Wi-Fi route was eligible for a write")
            }
            if let path = identity.regulatoryPath, identity.chip == "Broadcom BCM4378" {
                let plan = try Workflows.regionPlan(path: path, first: "TR", second: "US")
                let turkey = plan.locales.regions["TR"]?.bands["5 GHz"]?.channelBlocksByWidthMhz["20"]?.centers
                let usa = plan.locales.regions["US"]?.bands["5 GHz"]?.channelBlocksByWidthMhz["20"]?.centers
                try require(turkey?.isEmpty == false && usa?.isEmpty == false, "Country parser returned empty 5 GHz plans")
                for decoder in [Inspection.firmware, .microcode, .board] {
                    let text = try Workflows.inspect(decoder, identity: identity, file: nil, layout: CaptureLayout())
                    _ = try JSONSerialization.jsonObject(with: Data(text.utf8))
                }
                print("Read the selected firmware, microcode and board profiles; TR/US channel 144: \(turkey?.contains(144) == true)/\(usa?.contains(144) == true)")
            }
            if let start = radio.rawChannels, radio.channels?.reports.contains(where: \.switchTime) == true {
                let after = try ToolRunner.run(Resources.helper("read_wifi_airtime"), ["--channel-switch"])
                let timing = try Workflows.compareTiming(before: start, after: after, budget: "2")
                try require(!timing.reports.isEmpty, "Channel timing delta did not return reports")
                print("Channel timing reports: \(timing.reports.count)")
            }
            if let airtime = radio.airtime?.airtimePercent("Interface Average CCA") {
                print("Overall channel busy: \(airtime)%")
            }

            for service in ServiceClass.allCases {
                let socket = try Workflows.checkSocket(service: service, pace: 125_000)
                try require(socket.service == service.value && socket.bytesPerSecond == 125_000,
                            "Socket options did not read back for \(service.rawValue)")
            }
            print("All \(ServiceClass.allCases.count) socket priorities and pacing verified")

            let transfer = try Workflows.transfer(recovery: true)
            try require(transfer.preview.acknowledgedByDeadline <= transfer.preview.offered &&
                        transfer.archive.payloadBytesVerified == 1_048_576 &&
                        transfer.archive.attempts?.last?.receiverNextChunk == 40 &&
                        transfer.preview.paths.allSatisfy({ $0.interface == "lo0" }) &&
                        transfer.mismatchedKeyTlsStatus != nil, "Local archive recovery returned unexpected results")
            print("Loopback archive recovered at chunk 40: \(transfer.preview.acknowledgedByDeadline)/\(transfer.preview.offered) updates within deadline, mismatched key rejected")
            return 0
        } catch {
            FileHandle.standardError.write(Data("KYW self-test failed. \(error.localizedDescription)\n".utf8))
            return 1
        }
    }

    private static func require(_ passed: Bool, _ message: String) throws {
        guard passed else { throw KYWError(message) }
    }
}
