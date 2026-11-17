import SwiftUI

struct Spectrum: View {
    @ObservedObject var radio: RadioModel
    let open: (String) -> Void
    @State private var band: Band = .five
    @State private var width = 20
    @State private var from = ""
    @State private var to = "US"
    @State private var travelBand: Band = .five
    @State private var travelWidth = 20
    @State private var query: Comparison?
    @State private var error: String?
    @State private var comparing = false

    private struct Comparison {
        let first: String
        let second: String
        let plan: RegionPlan
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 19) {
            PageTitle(title: "Spectrum", detail: "Explore the channels on this Mac and compare the stored plans for two countries.")
            live
            travel
        }
        .task(id: radio.identity?.regulatoryPath) {
            if from.isEmpty { from = radio.reading?.status.country ?? "TR" }
            if query == nil, radio.identity?.regulatoryPath != nil { await compare() }
        }
    }

    private var live: some View {
        Panel {
            VStack(alignment: .leading, spacing: 14) {
                SectionTitle(title: "Available here", detail: "macOS’s current list by band and width. Frequencies shown are for primary channels.")
                if let link = radio.reading?.status {
                    HStack {
                        selectors(band: $band, width: $width)
                        Spacer()
                        Text(link.country.map { "Reported country \($0)" } ?? "Country unavailable")
                            .font(.caption).foregroundStyle(Palette.muted)
                    }
                    let channels = link.channels.filter { $0.band == band && $0.width == width }
                    let active = link.channel?.band == band ? link.channel?.number : nil
                    if channels.isEmpty {
                        Notice(text: "macOS returned no channels for \(band.rawValue) at \(width) MHz.")
                    } else {
                        channelGrid(channels.map(\.number), band: band, active: active)
                        Text("\(channels.count) primary channels\(active.map { " · Associated primary \($0)" } ?? "")")
                            .font(.caption).foregroundStyle(Palette.muted)
                    }
                } else {
                    LoadingResult(title: "Reading the current channels…")
                }
            }
        }
    }

    private var travel: some View {
        Panel {
            VStack(alignment: .leading, spacing: 14) {
                SectionTitle(title: "Travel channel planner", detail: "Find a channel block in both profiles for an access point you manage.")
                HStack(spacing: 13) {
                    TextField("Country A", text: $from).frame(width: 115)
                    Image(systemName: "arrow.left.arrow.right").foregroundStyle(Palette.muted).accessibilityHidden(true)
                    TextField("Country B", text: $to).frame(width: 115)
                    Button("Compare") { Task { await compare() } }
                        .buttonStyle(.borderedProminent)
                        .disabled(comparing || radio.identity?.regulatoryPath == nil)
                    if comparing { LoadingResult(title: "Reading the country table…") }
                }
                if let error {
                    Notice(text: error, warning: true)
                } else if radio.identity?.regulatoryPath == nil {
                    Notice(text: "No readable country table found for this Wi-Fi image.")
                }
                if let query {
                    Divider().overlay(Palette.edge)
                    HStack {
                        selectors(band: $travelBand, width: $travelWidth)
                        Spacer()
                        Text("Firmware country table").font(.caption).foregroundStyle(Palette.muted)
                    }
                    comparison(query)
                }
                Text("A block’s center can differ from its primary channel. The stored table helps you plan. When you arrive, check Available Here for what macOS offers.")
                    .font(.caption).foregroundStyle(Palette.muted)
                ResearchButton(title: "Country rules and channel 144") { open("clm-channel-tables.md") }
            }
        }
    }

    private func comparison(_ query: Comparison) -> some View {
        let width = String(travelWidth)
        let values = query.plan.locales
        let first = values.regions[query.first]?.bands[travelBand.rawValue]?.channelBlocksByWidthMhz[width]?.centers ?? []
        let second = values.regions[query.second]?.bands[travelBand.rawValue]?.channelBlocksByWidthMhz[width]?.centers ?? []
        let common = values.commonCentersByBandAndWidthMhz[travelBand.rawValue]?[width] ?? []
        let firstOnly = first.filter { !common.contains($0) }
        let secondOnly = second.filter { !common.contains($0) }
        return VStack(alignment: .leading, spacing: 13) {
            HStack {
                Stat(label: query.first + " blocks", value: String(first.count))
                Stat(label: query.second + " blocks", value: String(second.count))
                Stat(label: "Shared blocks", value: String(common.count), tone: Palette.mint)
            }
            if !common.isEmpty {
                Text("Shared centers").font(.caption.weight(.medium))
                channelGrid(common, band: travelBand)
            }
            if !firstOnly.isEmpty {
                Text("Centers only in \(query.first)").font(.caption.weight(.medium))
                channelGrid(firstOnly, band: travelBand)
            }
            if !secondOnly.isEmpty {
                Text("Centers only in \(query.second)").font(.caption.weight(.medium))
                channelGrid(secondOnly, band: travelBand)
            }
            if common.isEmpty {
                Notice(text: "These profiles have no shared blocks for \(travelBand.rawValue) at \(travelWidth) MHz.")
            }
        }
    }

    private func selectors(band: Binding<Band>, width: Binding<Int>) -> some View {
        HStack(spacing: 10) {
            Picker("Band", selection: band) {
                ForEach(Band.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented).labelsHidden().frame(width: 229)
            Picker("Channel width", selection: width) {
                ForEach([20, 40, 80, 160], id: \.self) { Text("\($0) MHz").tag($0) }
            }
            .labelsHidden().frame(width: 100)
        }
    }

    private func channelGrid(_ channels: [Int], band: Band, active: Int? = nil) -> some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 75), spacing: 7)], spacing: 7) {
            ForEach(channels, id: \.self) { number in
                let isActive = active == number
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 4) {
                        Text(String(number)).font(.system(size: 13, weight: .semibold, design: .monospaced))
                        if isActive {
                            Image(systemName: "location.fill")
                                .font(.system(size: 8)).accessibilityHidden(true)
                        }
                    }
                    Text("\(band.frequency(number)) MHz").font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(isActive ? Palette.mint : Palette.muted)
                        .lineLimit(1)
                }
                .padding(.horizontal, 9).padding(.vertical, 7)
                .frame(maxWidth: .infinity, alignment: .leading)
                .foregroundStyle(isActive ? Palette.mint : Palette.text)
                .background(isActive ? Palette.mint.opacity(0.13) : Palette.background,
                            in: RoundedRectangle(cornerRadius: 6))
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Channel \(number), \(band.frequency(number)) megahertz\(isActive ? ", associated primary" : "")")
            }
        }
    }

    @MainActor
    private func compare() async {
        guard !comparing, let path = radio.identity?.regulatoryPath else { return }
        let first = from.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        let second = to.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        comparing = true
        error = nil
        defer { comparing = false }
        do {
            let plan = try await Task.detached(priority: .utility) {
                try Workflows.regionPlan(path: path, first: first, second: second)
            }.value
            query = Comparison(first: first, second: second, plan: plan)
        } catch {
            self.error = error.localizedDescription
        }
    }
}
