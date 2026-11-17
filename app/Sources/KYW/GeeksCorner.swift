import AppKit
import SwiftUI

struct GeeksCorner: View {
    @ObservedObject var radio: RadioModel
    let open: (String) -> Void
    @State private var page: Page = .system

    private enum Page: String, CaseIterable, Identifiable {
        case system = "System"
        case controls = "Controls"
        case security = "ThreadX CVEs"
        case files = "Firmware files"
        var id: Self { self }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 19) {
            PageTitle(title: "Geek’s Corner", detail: "Meet the chip, see what it runs, and understand what you can change.")
            Picker("Geek’s Corner section", selection: $page) {
                ForEach(Page.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented).labelsHidden().frame(maxWidth: 485)
            switch page {
            case .system:
                if let identity = radio.identity {
                    identityView(identity)
                } else if let error = radio.identityError {
                    Panel {
                        VStack(alignment: .leading, spacing: 10) {
                            Notice(text: error, warning: true)
                            Button("Retry identification") { Task { await radio.identify() } }
                        }
                    }
                } else {
                    Panel { LoadingResult(title: "Reading device and firmware identity…") }
                }
            case .controls: Controls(radio: radio)
            case .security: AdvisoriesView()
            case .files: FirmwareFiles(identity: radio.identity, open: open)
            }
        }
    }

    private func identityView(_ identity: HardwareIdentity) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Panel {
                VStack(alignment: .leading, spacing: 16) {
                    SectionTitle(title: "Your radio stack", detail: identity.model + " · " + identity.systemVersion)
                    StackRow(symbol: "cpu", title: "Wi-Fi chip", value: identity.chip ?? "Unavailable",
                             detail: "The physical radio. It sends and receives Wi-Fi signals and has its own processor.",
                             source: [identity.board?.capitalized, identity.chipRevision.map { "Revision \($0)" },
                                      identity.pciID.map { "PCI \($0)" }].compactMap { $0 }.joined(separator: " · "))
                    Divider().overlay(Palette.edge)
                    StackRow(symbol: "internaldrive", title: "Firmware", value: identity.firmware ?? "Unavailable",
                             detail: "Broadcom’s program runs on the radio and handles work macOS hands to it.",
                             source: identity.firmwareID.map { "FWID \($0) · Live driver registry" } ?? "Live driver registry")
                    Divider().overlay(Palette.edge)
                    StackRow(symbol: "gearshape.2", title: "Real-time operating system", value: identity.threadX ?? "Unidentified",
                             detail: "Schedules jobs on the chip so time-sensitive radio work happens when it should.",
                             source: identity.threadX == nil ? "The selected image has no matching RTOS evidence in KYW."
                                : "Startup message in the selected firmware · Matched by SHA-256")
                    ResearchButton(title: "How ThreadX runs on the chip") { open("rtos-threadx.md") }
                }
            }
            Panel {
                VStack(alignment: .leading, spacing: 15) {
                    SectionTitle(title: "What the chip handles itself")
                    KeyValue(name: "During a connection", value: "Radio timing, frame retries, packet grouping and channel measurements.")
                    KeyValue(name: "When macOS prepares for sleep", value: "Selected address replies, existing TCP keepalives and wake filters can run on the chip. The exact sleep traffic on this build remains unmeasured.")
                    ResearchButton(title: "Read the sleep offload evidence") { open("sleep-network-offloads.md") }
                }
            }
            ReportedFeatures(roles: identity.roles, capabilities: identity.capabilities, open: open)
        }
    }
}

private struct StackRow: View {
    let symbol: String
    let title: String
    let value: String
    let detail: String
    let source: String

    var body: some View {
        HStack(alignment: .top, spacing: 13) {
            Image(systemName: symbol)
                .font(.system(size: 16, weight: .medium)).foregroundStyle(Palette.mint)
                .frame(width: 36, height: 36)
                .background(Palette.mint.opacity(0.09), in: RoundedRectangle(cornerRadius: 9))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 5) {
                Text(title).font(.caption).foregroundStyle(Palette.muted)
                Text(value).font(.system(size: 19, weight: .medium, design: .monospaced)).textSelection(.enabled)
                Text(detail).font(.system(size: 12))
                Text(source).font(.system(size: 10, weight: .medium, design: .monospaced)).foregroundStyle(Palette.muted)
            }
        }
    }
}

private struct ReportedFeatures: View {
    let roles: [InterfaceRole]
    let capabilities: [String]
    let open: (String) -> Void
    @State private var search = ""

    var body: some View {
        Panel {
            VStack(alignment: .leading, spacing: 13) {
                SectionTitle(title: "Driver interfaces and feature words",
                             detail: "These names come from the running driver. A reported capability can still depend on the OS, access point or a second device.")
                if !roles.isEmpty {
                    ForEach(roles) { role in
                        HStack {
                            Text(role.name).font(.system(size: 12, weight: .medium, design: .monospaced))
                            Spacer()
                            Text(role.role).font(.caption).foregroundStyle(Palette.muted)
                        }
                    }
                }
                if !capabilities.isEmpty {
                    DisclosureGroup("View \(capabilities.count) firmware feature words") {
                        VStack(alignment: .leading, spacing: 9) {
                            TextField("Filter feature words", text: $search)
                            Text(capabilities.filter { search.isEmpty || $0.localizedCaseInsensitiveContains(search) }
                                .joined(separator: "   "))
                                .font(.system(size: 12, design: .monospaced)).textSelection(.enabled)
                        }.padding(.top, 9)
                    }
                }
                ResearchButton(title: "Look up what these features mean") { open("firmware-feature-index.md") }
            }
        }
    }
}

private struct Controls: View {
    @ObservedObject var radio: RadioModel
    @State private var service: ServiceClass = .video
    @State private var pace = "125000"
    @State private var socketMessage: String?
    @State private var socketFailed = false
    @State private var channel: RadioChannel?
    @State private var pending: PendingChange?
    @State private var applying = false
    @State private var radioMessage: String?
    @State private var radioFailed = false

    private struct PendingChange: Identifiable {
        let title: String
        let detail: String
        let change: SystemRadio.Change
        var id: String { title }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            socket
            if let status = radio.reading?.status {
                radioControls(status)
            } else {
                Panel { LoadingResult(title: "Checking the radio and default routes…") }
            }
            Panel {
                VStack(alignment: .leading, spacing: 12) {
                    SectionTitle(title: "Managed by firmware and macOS", detail: "Read these to understand the radio’s decisions.")
                    KeyValue(name: "Transmit-power setting",
                             value: radio.reading?.status.osPowerValue.map { "Driver value \($0). This can represent automatic power. Actual output needs an RF measurement." } ?? "Power readout unavailable.")
                    KeyValue(name: "Country, antennas and sleep timing",
                             value: "The board profile, local channel rules, network and macOS decide what the radio can use.")
                    KeyValue(name: "ThreadX, registers and RAM",
                             value: "Firmware Files can inspect local files and saved diagnostic captures. Live access beyond these reports is unverified.")
                }
            }
        }
        .alert(item: $pending) { change in
            Alert(title: Text(change.title), message: Text(change.detail),
                  primaryButton: .default(Text("Apply")) { Task { await apply(change.change) } },
                  secondaryButton: .cancel())
        }
    }

    private var socket: some View {
        Panel {
            VStack(alignment: .leading, spacing: 13) {
                SectionTitle(title: "Traffic priority and pacing", detail: "Apply these settings to a fresh KYW TCP socket. KYW reads them back and closes the socket.")
                HStack(alignment: .firstTextBaseline, spacing: 13) {
                    Picker("Priority", selection: $service) {
                        ForEach(ServiceClass.allCases) { Text($0.rawValue).tag($0) }
                    }.frame(width: 215)
                    TextField("Bytes per second", text: $pace).frame(width: 105)
                        .accessibilityLabel("Pacing in bytes per second")
                    Text("bytes/s").font(.caption).foregroundStyle(Palette.muted)
                    Button("Apply and verify") { checkSocket() }.buttonStyle(.borderedProminent)
                }
                Text(service.effect).font(.caption).foregroundStyle(Palette.muted)
                Text("Pacing requests a send-rate cap for this socket. Lower rates give other traffic more room and can make uploads take longer.")
                    .font(.caption).foregroundStyle(Palette.muted)
                if let socketMessage { Notice(text: socketMessage, warning: socketFailed) }
            }
        }
    }

    private func radioControls(_ status: LinkStatus) -> some View {
        Panel {
            VStack(alignment: .leading, spacing: 13) {
                SectionTitle(title: "Detached radio controls", detail: "Use a wired test Mac to change the local radio without dropping your Wi-Fi internet connection.")
                Notice(text: status.radioControlReason, warning: !status.canChangeRadio)
                HStack(spacing: 12) {
                    Text("Radio power").font(.system(size: 13, weight: .medium))
                    Text(status.powerOn ? "On" : "Off").font(.caption).foregroundStyle(Palette.muted)
                    Spacer()
                    Button(status.powerOn ? "Turn radio off…" : "Turn radio on…") {
                        pending = PendingChange(
                            title: status.powerOn ? "Turn Wi-Fi radio off?" : "Turn Wi-Fi radio on?",
                            detail: status.powerOn ? "This stops Wi-Fi and direct wireless links on this Mac."
                                : "This starts the Wi-Fi radio. macOS may rejoin a saved network.",
                            change: .power(!status.powerOn)
                        )
                    }
                    .disabled(!status.canChangeRadio || applying)
                }
                Divider().overlay(Palette.edge)
                HStack(spacing: 12) {
                    Picker("Channel", selection: $channel) {
                        Text("Choose a supported channel").tag(nil as RadioChannel?)
                        ForEach(status.channels) { Text($0.label).tag(Optional($0)) }
                    }.frame(maxWidth: 385)
                        .disabled(!status.canChangeRadio || !status.powerOn || applying)
                    Spacer()
                    Button("Set channel…") {
                        guard let channel else { return }
                        pending = PendingChange(title: "Set the detached radio channel?",
                            detail: "This asks macOS to tune the detached radio to \(channel.label). Joining a network lets macOS choose the channel again.",
                            change: .channel(channel))
                    }
                    .disabled(!status.canChangeRadio || !status.powerOn || channel == nil || applying)
                }
                Text("Turning Wi-Fi off stops wireless links. A detached channel request tunes the idle radio. A joined network supplies its own channel.")
                    .font(.caption).foregroundStyle(Palette.muted)
                if let radioMessage { Notice(text: radioMessage, warning: radioFailed) }
            }
        }
    }

    private func checkSocket() {
        socketFailed = true
        guard let requested = UInt64(pace.trimmingCharacters(in: .whitespacesAndNewlines)), requested > 0 else {
            socketMessage = "Enter a positive whole number of bytes per second."
            return
        }
        do {
            let result = try Workflows.checkSocket(service: service, pace: requested)
            socketFailed = result.service != service.value || result.bytesPerSecond != requested
            socketMessage = socketFailed ? "macOS read back class \(result.service) and \(result.bytesPerSecond) bytes/s."
                : "Verified \(service.rawValue) and \(result.bytesPerSecond.formatted()) bytes/s on a KYW socket."
        } catch {
            socketMessage = error.localizedDescription
        }
    }

    @MainActor
    private func apply(_ change: SystemRadio.Change) async {
        applying = true
        defer { applying = false }
        do {
            try await Task.detached(priority: .userInitiated) { try SystemRadio.apply(change) }.value
            await radio.refresh()
            radioFailed = false
            radioMessage = "macOS accepted the request. The radio state above refreshes from the driver."
        } catch {
            radioFailed = true
            radioMessage = error.localizedDescription
        }
    }
}

private struct AdvisoriesView: View {
    @State private var advisories: ThreadXAdvisories?
    @State private var error: String?
    @State private var query = ""
    @State private var severity = "All severities"

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Panel {
                VStack(alignment: .leading, spacing: 12) {
                    SectionTitle(title: "ThreadX security advisories",
                                 detail: "A CVE identifies a publicly reported vulnerability. Each entry explains what can happen in the affected upstream component.")
                    Notice(text: "Applicability to the Broadcom firmware is unknown. Its patches and optional ThreadX components need vendor confirmation.", warning: true)
                    HStack {
                        if let advisories {
                            Link("Eclipse advisory list", destination: advisories.source)
                                .foregroundStyle(Palette.mint)
                            Text("\(advisories.rows.count) published CVEs · Checked \(advisories.checkedOn)")
                                .font(.caption).foregroundStyle(Palette.muted)
                        }
                    }
                }
            }
            if let advisories {
                let matches = advisories.rows.filter { item in
                    (severity == "All severities" || item.severity == severity) &&
                    (query.isEmpty || [item.cve, item.component, item.impact].contains { $0.localizedCaseInsensitiveContains(query) })
                }
                Panel {
                    VStack(alignment: .leading, spacing: 14) {
                        HStack(spacing: 12) {
                            TextField("Search by CVE or component", text: $query)
                            Picker("Severity", selection: $severity) {
                                Text("All severities").tag("All severities")
                                ForEach(Array(Set(advisories.rows.map(\.severity))).sorted(), id: \.self) {
                                    Text($0.capitalized).tag($0)
                                }
                            }.labelsHidden().frame(width: 143)
                        }
                        if matches.isEmpty { Notice(text: "No advisories match the search.") }
                        ForEach(matches) { item in
                            VStack(alignment: .leading, spacing: 6) {
                                Divider().overlay(Palette.edge)
                                HStack {
                                    Link(item.cve, destination: item.url)
                                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                        .foregroundStyle(Palette.mint)
                                    Text(item.component).foregroundStyle(Palette.muted).font(.caption)
                                    Spacer()
                                    Text(item.severity.capitalized)
                                        .foregroundStyle(item.severity == "high" ? Palette.amber : Palette.muted)
                                        .font(.caption.weight(.semibold))
                                }
                                Text(item.impact).font(.system(size: 12))
                                Text("Upstream range \(item.affected)\(item.fixed.map { " · Fixed in \($0)" } ?? "")")
                                    .font(.caption).foregroundStyle(Palette.muted).textSelection(.enabled)
                            }
                        }
                    }
                }
            } else if let error {
                Panel { Notice(text: error, warning: true) }
            }
        }
        .task {
            do { advisories = try Workflows.advisories() }
            catch { self.error = error.localizedDescription }
        }
    }
}
