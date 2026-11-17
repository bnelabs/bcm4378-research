import AppKit
import SwiftUI

@MainActor
final class RadioModel: ObservableObject {
    @Published private(set) var reading: RadioReading?
    @Published private(set) var identity: HardwareIdentity?
    @Published private(set) var identityError: String?
    @Published private(set) var history: [SignalPoint] = []
    @Published private(set) var isRefreshing = false

    struct SignalPoint: Identifiable {
        let time: Date
        let signal: Int
        var id: Date { time }
    }

    func poll() async {
        while !Task.isCancelled {
            await refresh()
            do {
                try await Task.sleep(for: .seconds(4))
            } catch {
                return
            }
        }
    }

    func refresh() async {
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        let current = await Task.detached(priority: .utility) { SystemRadio.reading() }.value
        guard !Task.isCancelled else { return }
        if let last = reading?.status, current.status.channel != last.channel {
            history.removeAll()
        }
        reading = current
        if let signal = current.status.rssi {
            history.append(SignalPoint(time: current.status.measuredAt, signal: signal))
            history = Array(history.suffix(60))
        }
    }

    func identify() async {
        do {
            identity = try await Task.detached(priority: .utility) { try SystemRadio.identity() }.value
            identityError = nil
        } catch {
            identityError = error.localizedDescription
        }
    }
}

enum Destination: String, CaseIterable, Identifiable {
    case overview = "Overview"
    case spectrum = "Spectrum"
    case lab = "Experiments"
    case geeks = "Geek’s Corner"
    case research = "Research"

    var id: Self { self }
    var symbol: String {
        switch self {
        case .overview: return "waveform.path"
        case .spectrum: return "chart.bar.xaxis"
        case .lab: return "testtube.2"
        case .geeks: return "cpu"
        case .research: return "book.closed"
        }
    }
}

@main
struct KYWApp: App {
    init() {
        if CommandLine.arguments.dropFirst().contains("--self-test") {
            exit(SmokeTest.run())
        }
    }

    var body: some Scene {
        Window("Know Your Wifi", id: "main") {
            Workspace()
                .frame(minWidth: 940, minHeight: 640)
                .preferredColorScheme(.dark)
        }
        .defaultSize(width: 1220, height: 825)
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentMinSize)
    }
}

struct Workspace: View {
    @StateObject private var radio = RadioModel()
    @StateObject private var transfers = TransferModel()
    @State private var destination: Destination = .overview
    @State private var note: String?

    var body: some View {
        HStack(spacing: 0) {
            sidebar
                .frame(width: 205)
                .background(Palette.sidebar)
            Rectangle().fill(Palette.edge).frame(width: 1)
            ScrollView {
                Group {
                    switch destination {
                    case .overview:
                        Overview(radio: radio, open: openNote)
                    case .spectrum:
                        Spectrum(radio: radio, open: openNote)
                    case .lab:
                        Experiments(radio: radio, transfers: transfers, open: openNote)
                    case .geeks:
                        GeeksCorner(radio: radio, open: openNote)
                    case .research:
                        Research(startingNote: note)
                    }
                }
                .frame(maxWidth: 1120)
                .padding(.horizontal, 34)
                .padding(.top, 43)
                .padding(.bottom, 36)
                .frame(maxWidth: .infinity, alignment: .top)
            }
            .id(destination)
            .background(Palette.background)
        }
        .foregroundStyle(Palette.text)
        .tint(Palette.mint)
        .task { await radio.poll() }
        .task { await radio.identify() }
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 22) {
            HStack(spacing: 11) {
                Image(systemName: "dot.radiowaves.left.and.right")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(Palette.mint)
                    .frame(width: 36, height: 36)
                    .background(Palette.mint.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Know Your Wifi").font(.system(size: 14, weight: .semibold))
                    Text("KYW").font(.system(size: 10, weight: .medium, design: .monospaced))
                        .tracking(1.8).foregroundStyle(Palette.muted)
                }
            }
            .padding(.horizontal, 6)

            VStack(spacing: 5) {
                ForEach(Destination.allCases) { page in
                    Button {
                        if page == .research, destination != .research { note = nil }
                        destination = page
                    } label: {
                        Label(page.rawValue, systemImage: page.symbol)
                            .labelStyle(SidebarLabelStyle())
                            .font(.system(size: 13, weight: page == destination ? .semibold : .medium))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 10)
                            .padding(.leading, 11)
                            .foregroundStyle(page == destination ? Palette.mint : Palette.muted)
                            .background(page == destination ? Palette.mint.opacity(0.11) : .clear,
                                        in: RoundedRectangle(cornerRadius: 8))
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityAddTraits(page == destination ? [.isSelected] : [])
                }
            }
            Spacer()
            if let status = radio.reading?.status {
                Divider().overlay(Palette.edge)
                VStack(alignment: .leading, spacing: 5) {
                    Text(radio.identity?.chip ?? "Wi-Fi interface")
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    HStack(spacing: 6) {
                        Circle().fill(status.carriesInternet ? Palette.mint : Palette.muted)
                            .frame(width: 5, height: 5).accessibilityHidden(true)
                        Text(status.carriesInternet ? "Default route on \(status.interface ?? "Wi-Fi")" : "Wi-Fi route \(status.interface ?? "unavailable")")
                            .font(.caption).foregroundStyle(Palette.muted)
                    }
                }.padding(.horizontal, 6)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 49)
        .padding(.bottom, 19)
        .frame(maxHeight: .infinity)
    }

    private func openNote(_ filename: String) {
        note = filename
        destination = .research
    }
}

private struct SidebarLabelStyle: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 10) {
            configuration.icon.frame(width: 16).accessibilityHidden(true)
            configuration.title
        }
    }
}

extension LinkStatus {
    var carriesInternet: Bool { interface.map(routes.contains) ?? false }
}
