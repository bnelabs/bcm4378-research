import SwiftUI

enum Palette {
    static let background = Color(red: 0.051, green: 0.071, blue: 0.096)
    static let sidebar = Color(red: 0.068, green: 0.091, blue: 0.122)
    static let panel = Color(red: 0.089, green: 0.116, blue: 0.153)
    static let edge = Color(red: 0.171, green: 0.215, blue: 0.267)
    static let text = Color(red: 0.922, green: 0.947, blue: 0.969)
    static let muted = Color(red: 0.640, green: 0.706, blue: 0.779)
    static let mint = Color(red: 0.406, green: 0.890, blue: 0.766)
    static let amber = Color(red: 0.984, green: 0.767, blue: 0.447)
}

struct PageTitle: View {
    let title: String
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.system(size: 35, weight: .semibold)).tracking(-1.1)
                .accessibilityAddTraits(.isHeader)
            Text(detail).font(.system(size: 13)).foregroundStyle(Palette.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct Panel<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) { self.content = content() }

    var body: some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(20)
            .background(Palette.panel, in: RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Palette.edge, lineWidth: 1))
    }
}

struct SectionTitle: View {
    let title: String
    var detail: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.system(size: 16, weight: .semibold)).accessibilityAddTraits(.isHeader)
            if let detail {
                Text(detail).font(.system(size: 12)).foregroundStyle(Palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

struct Stat: View {
    let label: String
    let value: String
    var unit: String? = nil
    var tone: Color = Palette.text

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label).font(.system(size: 12, weight: .medium)).foregroundStyle(Palette.muted)
            HStack(alignment: .firstTextBaseline, spacing: 5) {
                Text(value).font(.system(size: 26, weight: .medium, design: .monospaced))
                    .foregroundStyle(tone).lineLimit(1).minimumScaleFactor(0.7)
                if let unit {
                    Text(unit).font(.caption).foregroundStyle(Palette.muted).lineLimit(1)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct Notice: View {
    let text: String
    var warning = false

    var body: some View {
        Label(text, systemImage: warning ? "exclamationmark.circle" : "info.circle")
            .font(.system(size: 12))
            .foregroundStyle(warning ? Palette.amber : Palette.muted)
            .fixedSize(horizontal: false, vertical: true)
    }
}

struct LoadingResult: View {
    let title: String

    var body: some View {
        HStack(spacing: 9) {
            ProgressView().controlSize(.small)
            Text(title).font(.system(size: 12)).foregroundStyle(Palette.muted)
        }
    }
}

struct KeyValue: View {
    let name: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(name).foregroundStyle(Palette.muted).font(.system(size: 11, weight: .medium))
            Text(value).font(.system(size: 12, design: .monospaced)).textSelection(.enabled)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

struct ResearchButton: View {
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Label(title, systemImage: "doc.text.magnifyingglass")
        }
        .controlSize(.small)
    }
}
