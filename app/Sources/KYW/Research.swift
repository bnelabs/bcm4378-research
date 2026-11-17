import AppKit
import SwiftUI

struct Research: View {
    let startingNote: String?
    @State private var entries: [Entry] = []
    @State private var selected: Entry?
    @State private var group: Grouping = .notes
    @State private var search = ""

    private enum Grouping: String, CaseIterable, Identifiable {
        case notes = "Notes"
        case evidence = "Evidence"
        var id: Self { self }
        var folder: String { self == .notes ? "Docs" : "Evidence" }
    }

    private struct Entry: Identifiable {
        let url: URL
        let group: Grouping
        let title: String
        let body: String
        var id: String { url.lastPathComponent }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 19) {
            PageTitle(title: "Research library", detail: "Trace each finding to the experiment, file, or code it came from.")
            HStack(alignment: .top, spacing: 13) {
                Panel { list }.frame(width: 250)
                Panel {
                    if let selected { reader(selected) }
                    else { Notice(text: "Choose a note or an evidence file to open it.") }
                }
            }
        }
        .task {
            entries = loadEntries()
            selected = entries.first { $0.id == (startingNote ?? "capability-catalog.md") } ?? entries.first
        }
    }

    private var list: some View {
        VStack(alignment: .leading, spacing: 11) {
            Picker("Research files", selection: $group) {
                ForEach(Grouping.allCases) { Text($0.rawValue).tag($0) }
            }.pickerStyle(.segmented).labelsHidden()
            TextField("Search \(group.rawValue.lowercased())", text: $search)
            let matches = entries.filter {
                $0.group == group &&
                (search.isEmpty || $0.title.localizedCaseInsensitiveContains(search)
                  || (group == .notes && $0.body.localizedCaseInsensitiveContains(search)))
            }
            if matches.isEmpty { Notice(text: "No matching files.") }
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 4) {
                    ForEach(matches) { entry in
                        Button {
                            selected = entry
                        } label: {
                            Text(entry.title).font(.system(size: 12, weight: .medium))
                                .fixedSize(horizontal: false, vertical: true)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 8).padding(.vertical, 7)
                                .foregroundStyle(selected?.id == entry.id ? Palette.mint : Palette.text)
                                .background(selected?.id == entry.id ? Palette.mint.opacity(0.1) : .clear,
                                            in: RoundedRectangle(cornerRadius: 6))
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityAddTraits(selected?.id == entry.id ? [.isSelected] : [])
                    }
                }
            }.frame(height: 515)
            Text("\(matches.count) files").font(.caption).foregroundStyle(Palette.muted)
        }
    }

    private func reader(_ entry: Entry) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionTitle(title: entry.title)
            HStack {
                Text(entry.id).font(.caption.monospaced()).foregroundStyle(Palette.muted)
                Spacer()
                Button("Reveal file") { NSWorkspace.shared.activateFileViewerSelecting([entry.url]) }
                    .controlSize(.small)
            }
            Divider().overlay(Palette.edge)
            ScrollView {
                if entry.group == .notes {
                    NoteContent(markdown: entry.body, baseURL: entry.url)
                } else {
                    Text(String(entry.body.prefix(50_000)))
                        .font(.system(size: 11, design: .monospaced))
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if entry.body.count > 50_000 {
                        Notice(text: "Reveal the file to read the complete JSON.")
                    }
                }
            }
            .id(entry.id)
            .frame(height: 550)
        }
        .environment(\.openURL, OpenURLAction { url in
            if url.isFileURL, let destination = entries.first(where: { $0.id == url.lastPathComponent }) {
                selected = destination
                group = destination.group
                search = ""
                return .handled
            }
            if url.isFileURL, url.deletingLastPathComponent().lastPathComponent.lowercased() == "tools",
               let base = URL(string: "https://github.com/bnelabs/bcm4378-research/blob/main/tools/") {
                return .systemAction(base.appendingPathComponent(url.lastPathComponent))
            }
            if ["http", "https"].contains(url.scheme ?? "") { return .systemAction }
            return .discarded
        })
    }

    private func loadEntries() -> [Entry] {
        Grouping.allCases.flatMap { group in
            let folder = Resources.folder.appendingPathComponent(group.folder, isDirectory: true)
            let urls = (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? []
            return urls.compactMap { url -> Entry? in
                let ext = group == .notes ? "md" : "json"
                guard url.pathExtension == ext, let text = try? String(contentsOf: url, encoding: .utf8) else { return nil }
                let name = url.deletingPathExtension().lastPathComponent
                let heading = text.split(separator: "\n", maxSplits: 1).first.flatMap { line in
                    line.hasPrefix("# ") ? String(line.dropFirst(2)) : nil
                }
                let fallback = String(name.dropFirst(name.hasPrefix("2026-11-17-") ? 11 : 0))
                    .replacingOccurrences(of: "-", with: " ").capitalized
                return Entry(url: url, group: group, title: heading ?? fallback, body: text)
            }.sorted { $0.title.localizedStandardCompare($1.title) == .orderedAscending }
        }
    }
}

private struct NoteContent: View {
    let markdown: String
    let baseURL: URL

    private enum Block {
        case heading(String)
        case paragraph(String)
        case code(String)
        case table([[String]])
    }

    var body: some View {
        LazyVStack(alignment: .leading, spacing: 11) {
            ForEach(Array(blocks.enumerated()), id: \.offset) { _, block in
                switch block {
                case .heading(let text):
                    Text(inline(text)).font(.system(size: 15, weight: .semibold))
                        .accessibilityAddTraits(.isHeader).padding(.top, 5)
                case .paragraph(let text):
                    Text(inline(text)).font(.system(size: 12)).lineSpacing(3).textSelection(.enabled)
                case .code(let code):
                    ScrollView(.horizontal) {
                        Text(code).font(.system(size: 11, design: .monospaced)).textSelection(.enabled).padding(10)
                    }
                    .background(Palette.background, in: RoundedRectangle(cornerRadius: 6))
                case .table(let rows):
                    table(rows)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var blocks: [Block] {
        var parsed: [Block] = []
        var content: [String] = []
        var code = false
        func flush() {
            guard !content.isEmpty else { return }
            if code {
                parsed.append(.code(content.joined(separator: "\n")))
            } else if content.count > 1, content.allSatisfy({ $0.hasPrefix("|") }) {
                let rows = content.map { row in
                    row.split(separator: "|", omittingEmptySubsequences: false).dropFirst().dropLast()
                        .map { $0.trimmingCharacters(in: .whitespaces) }
                }
                parsed.append(.table(rows.enumerated().filter { $0.offset != 1 }.map(\.element)))
            } else {
                parsed.append(.paragraph(content.joined(separator: "\n")))
            }
            content.removeAll(keepingCapacity: true)
        }
        for (index, line) in markdown.components(separatedBy: .newlines).enumerated() {
            if line.hasPrefix("```") {
                flush()
                code.toggle()
            } else if code {
                content.append(line)
            } else if line.hasPrefix("#") {
                flush()
                if index > 0 { parsed.append(.heading(String(line.drop(while: { $0 == "#" || $0 == " " })))) }
            } else if line.isEmpty {
                flush()
            } else {
                content.append(line)
            }
        }
        flush()
        return parsed
    }

    private func inline(_ text: String) -> AttributedString {
        (try? AttributedString(markdown: text, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace),
                               baseURL: baseURL)) ?? AttributedString(text)
    }

    private func table(_ rows: [[String]]) -> some View {
        let width: CGFloat = (rows.first?.count ?? 0) <= 2 ? 210 : 151
        return ScrollView(.horizontal) {
            Grid(alignment: .topLeading, horizontalSpacing: 0, verticalSpacing: 0) {
                ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
                    GridRow {
                        ForEach(Array(row.enumerated()), id: \.offset) { _, cell in
                            Text(inline(cell))
                                .font(.system(size: 11, weight: index == 0 ? .semibold : .regular))
                                .textSelection(.enabled)
                                .frame(width: width, alignment: .leading)
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(8)
                        }
                    }
                    .background(index == 0 ? Palette.mint.opacity(0.11) : (index.isMultiple(of: 2) ? Palette.background : .clear))
                }
            }
        }
        .background(Palette.background, in: RoundedRectangle(cornerRadius: 6))
    }
}
