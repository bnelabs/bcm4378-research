import AppKit
import SwiftUI

@MainActor
final class TransferModel: ObservableObject {
    @Published private(set) var busy: String?
    @Published private(set) var result: TransferResult?
    @Published private(set) var message: String?
    @Published private(set) var failed = false

    func run(recovery: Bool, key: URL? = nil, mode: TransferMode = .lan, interface: String = "en0") async {
        guard busy == nil else { return }
        busy = key == nil ? "Testing on this Mac…" : "Finding your paired Mac and running both streams…"
        message = nil
        result = nil
        defer { busy = nil }
        do {
            result = try await Task.detached(priority: .userInitiated) {
                try Workflows.transfer(recovery: recovery, peer: key, mode: mode, interface: interface)
            }.value
        } catch {
            failed = true
            message = error.localizedDescription
        }
    }

    func listen(_ key: URL) async {
        guard busy == nil else { return }
        busy = "Waiting for the paired Mac for up to 90 seconds…"
        message = nil
        result = nil
        defer { busy = nil }
        do {
            try await Task.detached(priority: .userInitiated) { try Workflows.listen(key: key) }.value
            failed = false
            message = "The pairing window ended. View transfer results on the sender."
        } catch {
            failed = true
            message = error.localizedDescription
        }
    }
}

struct Experiments: View {
    @ObservedObject var radio: RadioModel
    @ObservedObject var transfers: TransferModel
    let open: (String) -> Void
    @State private var key: URL?
    @State private var mode: TransferMode = .split
    @State private var keyError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 19) {
            PageTitle(title: "Experiments", detail: "Measure radio switches and see whether urgent work meets its deadline during a transfer.")
            TimingExperiment(radio: radio, open: open)
            transferPanel
        }
    }

    private var transferPanel: some View {
        Panel {
            VStack(alignment: .leading, spacing: 14) {
                SectionTitle(title: "Keep the fast stream moving", detail: "Send short updates alongside a bulk archive. See which updates meet their deadline and how the archive recovers after its connection drops.")
                HStack(spacing: 9) {
                    Button("Test on this Mac") { Task { await transfers.run(recovery: false) } }
                        .buttonStyle(.borderedProminent)
                    Button("Test archive recovery") { Task { await transfers.run(recovery: true) } }
                }
                .disabled(transfers.busy != nil)
                Text("The local tests use generated data on loopback. Recovery closes just the test’s archive connection.")
                    .font(.caption).foregroundStyle(Palette.muted)
                if let busy = transfers.busy { LoadingResult(title: busy) }
                if let message = transfers.message { Notice(text: message, warning: transfers.failed) }
                if let result = transfers.result { transferResult(result) }
                Divider().overlay(Palette.edge)
                DisclosureGroup("Run the same workload with a paired Mac") {
                    VStack(alignment: .leading, spacing: 11) {
                        Text("Use the same key file on two Macs you manage. Start listening on one, then run the test on the other. The direct mode asks for an Apple peer Wi-Fi link for updates and ordinary Wi-Fi for the archive.")
                            .font(.caption).foregroundStyle(Palette.muted)
                        HStack {
                            Button("Create key…") { makeKey() }
                            Button("Choose key…") {
                                if let selected = selectFile() { key = selected }
                                keyError = nil
                            }
                            if let key { Text(key.lastPathComponent).font(.caption).foregroundStyle(Palette.muted) }
                        }
                        if let keyError { Notice(text: keyError, warning: true) }
                        Picker("Sender path", selection: $mode) {
                            ForEach(TransferMode.allCases) { Text($0.label).tag($0) }
                        }.frame(maxWidth: 325)
                        HStack {
                            Button("Listen for 90 seconds") {
                                guard let key else { return }
                                Task { await transfers.listen(key) }
                            }
                            Button("Run paired transfer") {
                                guard let key, let adapter = radio.reading?.status.interface else { return }
                                let chosen = mode
                                Task { await transfers.run(recovery: false, key: key, mode: chosen, interface: adapter) }
                            }
                            .disabled(radio.reading?.status.interface == nil)
                        }
                        .disabled(key == nil || transfers.busy != nil)
                        Text("KYW checks the shared key and reports which interfaces carried the test traffic.")
                            .font(.caption).foregroundStyle(Palette.muted)
                    }.padding(.top, 10)
                }
                ResearchButton(title: "Read the paired experiment") { open("practical-radio-applications.md") }
            }
        }
    }

    private func transferResult(_ result: TransferResult) -> some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack(spacing: 12) {
                Stat(label: "Updates within 160 ms", value: "\(result.preview.acknowledgedByDeadline)/\(result.preview.offered)",
                     tone: Palette.mint)
                Stat(label: "95% of replies within", value: result.preview.roundTripP95Ms.formatted(.number.precision(.fractionLength(1))),
                     unit: "ms")
                Stat(label: "Archive verified", value: (result.archive.payloadBytesVerified / 1024).formatted(), unit: "KiB")
            }
            let previewInterfaces = Set(result.preview.paths.map(\.interface)).sorted().joined(separator: ", ")
            let archivePaths = result.archive.paths + (result.archive.attempts ?? []).flatMap(\.paths)
            let archiveInterfaces = Set(archivePaths.map(\.interface)).sorted().joined(separator: ", ")
            Text("Updates on \(previewInterfaces) · Archive on \(archiveInterfaces)")
                .font(.caption.monospaced()).foregroundStyle(Palette.muted)
            if let updates = result.previewsAcknowledgedBetweenArchiveAttempts {
                let offset = result.archive.attempts?.last?.receiverNextChunk ?? 0
                Notice(text: "The archive resumed from verified chunk \(offset). \(updates) updates arrived between archive attempts.")
            }
            if result.mismatchedKeyTlsStatus != nil {
                Notice(text: "The test rejected a connection with a different key.")
            }
        }
        .padding(13)
        .background(Palette.background, in: RoundedRectangle(cornerRadius: 8))
    }

    @MainActor
    private func makeKey() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "kyw-pairing.key"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            try Workflows.makeKey(at: url)
            key = url
            keyError = nil
        } catch {
            keyError = error.localizedDescription
        }
    }
}

private struct TimingExperiment: View {
    @ObservedObject var radio: RadioModel
    let open: (String) -> Void
    @State private var start: Snapshot?
    @State private var comparison: TimingComparison?
    @State private var budget = "2"
    @State private var visits: [Visit] = []
    @State private var error: String?
    @State private var comparing = false

    private struct Snapshot {
        let raw: Data
        let sample: ReportSample
    }

    private struct Visit: Identifiable {
        let id: String
        let label: String
        let added: Int64
    }

    var body: some View {
        Panel {
            VStack(alignment: .leading, spacing: 13) {
                SectionTitle(title: "Channel switch timing", detail: "Start a measurement, use Wi-Fi as usual, then compare. See how long the driver spent on a channel and how quickly it switched.")
                HStack(spacing: 10) {
                    Button(start == nil ? "Start measurement" : "Restart measurement") {
                        start = current()
                        comparison = nil
                        visits = []
                        error = nil
                    }
                    .disabled(current() == nil || comparing)
                    TextField("Delay target (ms)", text: $budget)
                        .frame(width: 82).accessibilityLabel("Delay target in milliseconds")
                    Text("ms target").font(.caption).foregroundStyle(Palette.muted)
                    Button("Compare now") { Task { await finish() } }
                        .buttonStyle(.borderedProminent)
                        .disabled(!canCompare || comparing)
                }
                if comparing { LoadingResult(title: "Comparing driver histograms…") }
                if let start {
                    Text("Started at \(start.sample.measuredAt.formatted(date: .omitted, time: .standard))\(canCompare ? "" : " · Waiting for the next sample")")
                        .font(.caption).foregroundStyle(Palette.muted)
                } else if current() == nil {
                    Notice(text: "Channel-switch reports are unavailable on this driver.")
                }
                if let comparison { timingResult(comparison) }
                if let error { Notice(text: error, warning: true) }
                ResearchButton(title: "Read the dual-band measurement") { open("simultaneous-dual-band.md") }
            }
        }
    }

    private var canCompare: Bool {
        guard let start, let current = current() else { return false }
        return current.sample.measuredAt > start.sample.measuredAt
    }

    private func current() -> Snapshot? {
        guard let raw = radio.reading?.rawChannels, let sample = radio.reading?.channels,
              sample.reports.contains(where: \.switchTime) else { return nil }
        return Snapshot(raw: raw, sample: sample)
    }

    private func timingResult(_ report: TimingComparison) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            if let seconds = report.elapsedSeconds {
                Text("\(seconds.formatted(.number.precision(.fractionLength(1)))) seconds observed")
                    .font(.caption).foregroundStyle(Palette.muted)
            }
            ForEach(report.reports) { line in
                HStack(spacing: 10) {
                    Text("\(line.group) · \(line.report == "Dwell Time" ? "Time on channel" : "Retune time")")
                        .font(.caption)
                    Spacer()
                    Text("\(line.events) records").font(.caption).foregroundStyle(Palette.muted)
                    Text(line.p95.map { bounds($0) + " " + line.unit } ?? "—")
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                        .frame(width: 110, alignment: .trailing)
                        .accessibilityLabel("95th percentile \(line.p95.map(bounds) ?? "unavailable") \(line.unit)")
                    Text(line.overBudgetCountRange.map { bounds($0) + " over target" } ?? "—")
                        .font(.caption).foregroundStyle(Palette.muted)
                        .frame(width: 113, alignment: .trailing)
                }
            }
            if !visits.isEmpty {
                Text("New channel records").font(.caption.weight(.semibold))
                Text(visits.map { "\($0.label) +\($0.added)" }.joined(separator: " · "))
                    .font(.caption.monospaced()).foregroundStyle(Palette.muted)
            }
            Text("Timing values are bounds for the 95th percentile of the driver’s records. The records show visits to other channels without measuring simultaneous airtime.")
                .font(.caption).foregroundStyle(Palette.muted)
            if !report.unpairedHistograms.isEmpty {
                Notice(text: "Some histograms appeared in only one sample and were skipped.", warning: true)
            }
        }
        .padding(13)
        .background(Palette.background, in: RoundedRectangle(cornerRadius: 8))
    }

    private func bounds<T: BinaryInteger>(_ range: [T]) -> String {
        guard range.count == 2 else { return "—" }
        return range[0] == range[1] ? String(range[0]) : "\(range[0])–\(range[1])"
    }

    @MainActor
    private func finish() async {
        guard !comparing, let start, let stop = current(), canCompare else { return }
        let target = budget.trimmingCharacters(in: .whitespacesAndNewlines)
        comparing = true
        error = nil
        defer { comparing = false }
        do {
            comparison = try await Task.detached(priority: .utility) {
                try Workflows.compareTiming(before: start.raw, after: stop.raw, budget: target)
            }.value
            visits = stop.sample.reports.compactMap { row in
                guard row.subgroup == "Channels Visited", let value = row.value,
                      let previous = start.sample.value(row.group, row.subgroup, row.name),
                      previous >= 0, value > previous else { return nil }
                return Visit(id: row.id, label: "\(row.group) \(row.name)", added: value - previous)
            }
        } catch {
            self.error = error.localizedDescription
        }
    }
}
