import AppKit
import Charts
import SwiftUI

struct Overview: View {
    @ObservedObject var radio: RadioModel
    let open: (String) -> Void
    @State private var reference: LinkStatus?
    @State private var exportError: String?

    private struct AirMetric: Identifiable {
        let label: String
        let key: String
        let tone: Color
        var id: String { key }
    }

    private let metrics: [AirMetric] = [
        .init(label: "Overall busy", key: "Interface Average CCA", tone: Palette.mint),
        .init(label: "Same Wi-Fi network", key: "Interface IBSS CCA", tone: Color(red: 0.47, green: 0.67, blue: 0.98)),
        .init(label: "Overlapping networks", key: "Interface OBSS CCA", tone: Palette.amber),
        .init(label: "Interference", key: "Interface Interference CCA", tone: Color(red: 0.85, green: 0.61, blue: 0.9))
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 19) {
            HStack(alignment: .top) {
                PageTitle(title: "Wi-Fi overview", detail: "See the link your Mac is using and what the radio is hearing.")
                Button {
                    Task { await radio.refresh() }
                } label: {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
                .disabled(radio.isRefreshing)
                .padding(.top, 6)
            }
            if let reading = radio.reading {
                link(reading.status)
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .top, spacing: 14) {
                        signal(reading.status).frame(minWidth: 350)
                        airtime(reading.airtime).frame(width: 302)
                    }
                    VStack(spacing: 14) {
                        signal(reading.status)
                        airtime(reading.airtime)
                    }
                }
                if let message = reading.reportNotice { Notice(text: message, warning: true) }
                HStack {
                    Label("Sampled \(reading.status.measuredAt.formatted(date: .omitted, time: .standard))", systemImage: "clock")
                        .font(.caption).foregroundStyle(Palette.muted)
                    Spacer()
                    Button("Save link snapshot…") { export(reading.status) }
                        .controlSize(.small)
                }
                if let exportError { Notice(text: exportError, warning: true) }
            } else {
                Panel { LoadingResult(title: "Reading your Wi-Fi interface…") }
            }
        }
    }

    private func link(_ status: LinkStatus) -> some View {
        Panel {
            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 13) {
                    Image(systemName: status.channel == nil ? "wifi.slash" : "wifi")
                        .font(.system(size: 21, weight: .medium))
                        .foregroundStyle(Palette.mint)
                        .frame(width: 43, height: 43)
                        .background(Palette.mint.opacity(0.12), in: RoundedRectangle(cornerRadius: 11))
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(status.channel?.label ?? (status.powerOn ? "Wi-Fi has no associated channel" : "Wi-Fi radio off"))
                            .font(.system(size: 19, weight: .semibold))
                        Text(linkDetail(status)).font(.caption).foregroundStyle(Palette.muted)
                    }
                    Spacer()
                    if let country = status.country, !country.isEmpty {
                        KeyValue(name: "Reported country", value: country)
                            .fixedSize(horizontal: true, vertical: false)
                    }
                }
                Divider().overlay(Palette.edge)
                HStack(spacing: 16) {
                    Stat(label: "Signal", value: status.rssi.map(String.init) ?? "—", unit: "dBm", tone: Palette.mint)
                    Stat(label: "Noise", value: status.noise.map(String.init) ?? "—", unit: "dBm")
                    Stat(label: "Signal over noise", value: status.snr.map(String.init) ?? "—", unit: "dB")
                    Stat(label: "Transmit link rate", value: status.rate?.formatted(.number.precision(.fractionLength(0...1))) ?? "—", unit: "Mb/s")
                }
            }
        }
    }

    private func linkDetail(_ status: LinkStatus) -> String {
        var parts = [status.phy, status.interface].compactMap { $0 }
        if status.carriesInternet { parts.append("Carries the default route") }
        return parts.isEmpty ? status.mode : parts.joined(separator: " · ")
    }

    private func signal(_ status: LinkStatus) -> some View {
        Panel {
            VStack(alignment: .leading, spacing: 13) {
                SectionTitle(title: "Signal history", detail: "Compare two spots before moving an access point.")
                if radio.history.count > 1 {
                    signalChart
                } else {
                    VStack(alignment: .leading, spacing: 8) {
                        Image(systemName: "waveform").foregroundStyle(Palette.mint)
                        Text(status.rssi == nil ? "Signal readings need an active Wi-Fi link." : "The signal trace starts after the second reading.")
                            .font(.caption).foregroundStyle(Palette.muted)
                    }
                    .frame(maxWidth: .infinity, minHeight: 143, alignment: .center)
                }
                HStack(alignment: .center) {
                    if let change = signalChange(status) {
                        Text(change).font(.caption.monospacedDigit()).foregroundStyle(Palette.mint)
                    } else if reference != nil {
                        Text("Channel changed since the pinned sample.")
                            .font(.caption).foregroundStyle(Palette.muted)
                    }
                    Spacer()
                    Button(reference == nil ? "Pin this reading" : "Pin again") { reference = status }
                        .disabled(status.rssi == nil)
                        .controlSize(.small)
                }
            }
        }
    }

    private var signalChart: some View {
        Chart(radio.history) { sample in
            AreaMark(x: .value("Time", sample.time), yStart: .value("Chart floor", -100),
                     yEnd: .value("Signal dBm", sample.signal))
                .foregroundStyle(.linearGradient(colors: [Palette.mint.opacity(0.29), Palette.mint.opacity(0.02)],
                                                 startPoint: .top, endPoint: .bottom))
            LineMark(x: .value("Time", sample.time), y: .value("Signal dBm", sample.signal))
                .foregroundStyle(Palette.mint)
                .lineStyle(StrokeStyle(lineWidth: 2))
        }
        .chartYScale(domain: -100 ... -15)
        .chartYAxis {
            AxisMarks(position: .leading, values: [-100, -80, -60, -40, -20]) {
                AxisGridLine().foregroundStyle(Palette.edge)
                AxisValueLabel().foregroundStyle(Palette.muted)
            }
        }
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 4)) {
                AxisValueLabel(format: .dateTime.hour().minute().second()).foregroundStyle(Palette.muted)
            }
        }
        .frame(height: 143)
        .accessibilityLabel("Recent Wi-Fi signal readings in dBm")
    }

    private func signalChange(_ status: LinkStatus) -> String? {
        guard let reference, reference.channel == status.channel,
              let current = status.rssi, let previous = reference.rssi else { return nil }
        return "\(current - previous >= 0 ? "+" : "")\(current - previous) dB from pinned reading"
    }

    private func airtime(_ sample: ReportSample?) -> some View {
        Panel {
            VStack(alignment: .leading, spacing: 14) {
                SectionTitle(title: "Channel airtime", detail: "How often the radio senses a busy channel.")
                ForEach(metrics) { metric in
                    let value = sample?.airtimePercent(metric.key)
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(metric.label).font(.caption)
                            Spacer()
                            Text(value.map { "\($0)%" } ?? "—")
                                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                                .foregroundStyle(metric.tone)
                        }
                        GeometryReader { size in
                            Capsule().fill(Palette.edge)
                            if let value {
                                Capsule().fill(metric.tone)
                                    .frame(width: size.size.width * Double(value) / 100)
                            }
                        }
                        .frame(height: 4)
                        .accessibilityHidden(true)
                    }
                    .accessibilityElement(children: .combine)
                }
                Text("Driver categories update independently and can repeat between reads.")
                    .font(.caption).foregroundStyle(Palette.muted)
                ResearchButton(title: "Read the measurement notes") { open("live-wifi-airtime.md") }
            }
        }
    }

    @MainActor
    private func export(_ status: LinkStatus) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "kyw-link-snapshot.json"
        guard panel.runModal() == .OK, let destination = panel.url else { return }
        do {
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            try encoder.encode(status).write(to: destination, options: .atomic)
            exportError = nil
        } catch {
            exportError = error.localizedDescription
        }
    }
}
