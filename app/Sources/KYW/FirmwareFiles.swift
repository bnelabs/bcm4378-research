import AppKit
import SwiftUI

struct FirmwareFiles: View {
    let identity: HardwareIdentity?
    let open: (String) -> Void
    @State private var selection: Inspection = .firmware
    @State private var file: URL?
    @State private var layout = CaptureLayout()
    @State private var result: String?
    @State private var resultTitle = ""
    @State private var error: String?
    @State private var working = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let identity { installed(identity) }
            Panel {
                VStack(alignment: .leading, spacing: 13) {
                    SectionTitle(title: "Inspect a file", detail: "The decoders read installed files and saved captures offline.")
                    Picker("Decoder", selection: $selection) {
                        ForEach(Inspection.allCases) { Text($0.rawValue).tag($0) }
                    }.frame(maxWidth: 362)
                    Text(selection.effect).font(.caption).foregroundStyle(Palette.muted)
                    if selection.needsFile {
                        HStack {
                            Button("Choose a saved file…") { file = selectFile() ?? file }
                            if let file { Text(file.lastPathComponent).font(.caption).foregroundStyle(Palette.muted) }
                        }
                    }
                    if selection == .savedRAM { captureFields }
                    HStack {
                        Button("Inspect") { Task { await inspect() } }
                            .buttonStyle(.borderedProminent)
                            .disabled(working || (selection.needsFile && file == nil))
                        if working { LoadingResult(title: "Running the offline decoder…") }
                    }
                    if let error { Notice(text: error, warning: true) }
                }
            }
            if let result {
                Panel {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            SectionTitle(title: resultTitle)
                            Spacer()
                            Button("Copy JSON") {
                                NSPasteboard.general.clearContents()
                                NSPasteboard.general.setString(result, forType: .string)
                            }
                        }
                        ScrollView([.vertical, .horizontal]) {
                            Text(result)
                                .font(.system(size: 11, design: .monospaced))
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .textSelection(.enabled)
                                .padding(13)
                        }
                        .frame(maxHeight: 310)
                        .background(Palette.background, in: RoundedRectangle(cornerRadius: 8))
                    }
                }
            }
        }
        .onChange(of: selection) {
            file = nil
            error = nil
        }
    }

    private func installed(_ identity: HardwareIdentity) -> some View {
        Panel {
            VStack(alignment: .leading, spacing: 12) {
                SectionTitle(title: "Files requested by the driver", detail: "The executable runs on the chip. The other files supply board settings and radio limits.")
                if let path = identity.firmwarePath {
                    KeyValue(name: "Firmware image", value: path)
                    if let resolved = identity.resolvedFirmwarePath, path != resolved {
                        KeyValue(name: "Resolved image", value: resolved)
                    }
                    if let digest = identity.firmwareDigest { KeyValue(name: "SHA-256", value: digest) }
                } else {
                    Notice(text: "The running driver did not provide a readable image path.")
                }
                if let path = identity.boardSettingsPath { KeyValue(name: "Board settings (NVRAM)", value: path) }
                if let path = identity.regulatoryPath { KeyValue(name: "Country rules (CLM)", value: path) }
                if let path = identity.powerCapsPath { KeyValue(name: "Transmit-power caps", value: path) }
                HStack {
                    if let path = identity.resolvedFirmwarePath {
                        Button("Reveal image in Finder") {
                            NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
                        }
                        .controlSize(.small)
                    }
                    ResearchButton(title: "Read the firmware layout") { open("firmware-layout.md") }
                }
            }
        }
    }

    private var captureFields: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Use the byte counts from the driver that produced the capture.")
                .font(.caption).foregroundStyle(Palette.muted)
            HStack(spacing: 10) {
                captureField("Total RAM bytes", value: $layout.total)
                captureField("Save/restore bytes", value: $layout.retained)
                captureField("Prefix bytes", value: $layout.prefix)
            }
            ResearchButton(title: "Check the capture formats") { open("ram-diagnostics.md") }
        }
    }

    private func captureField(_ name: String, value: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(name).font(.caption).foregroundStyle(Palette.muted)
            TextField(name, text: value).labelsHidden().frame(maxWidth: 142)
        }
    }

    @MainActor
    private func inspect() async {
        guard !working else { return }
        let selection = selection, identity = identity, file = file, layout = layout
        working = true
        error = nil
        defer { working = false }
        do {
            result = try await Task.detached(priority: .utility) {
                try Workflows.inspect(selection, identity: identity, file: file, layout: layout)
            }.value
            resultTitle = selection.rawValue
        } catch {
            self.error = error.localizedDescription
        }
    }
}

@MainActor
func selectFile() -> URL? {
    let panel = NSOpenPanel()
    panel.canChooseDirectories = false
    panel.allowsMultipleSelection = false
    return panel.runModal() == .OK ? panel.url : nil
}
