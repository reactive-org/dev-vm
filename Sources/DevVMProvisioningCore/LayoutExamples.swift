import Foundation

public enum LayoutExampleID: String, Codable, CaseIterable, Sendable {
    case fourTerminals = "four-terminals"
    case terminalBrowser = "terminal-browser"
    case vscodeBrowser = "vscode-browser"
    case claudeWorkspace = "claude-two-terminals-browser"
    case multiWorkspace = "multi-workspace"
    case claudeBrowserCodeTerminals = "claude-browser-code-terminals"
    case smallScreen = "small-screen"
}
public struct LayoutExampleWindow: Decodable, Sendable {
    public enum Kind: String, Decodable, Sendable { case terminal, browser, editor, claude }
    public let label: String
    public let kind: Kind
    public let x: Double, y: Double, width: Double, height: Double
    public let floating: Bool?
    /// Omarchy workspace the window opens on; absent means workspace 1.
    public let workspace: Int?
    public var workspaceNumber: Int { workspace ?? 1 }
}
public struct LayoutExample: Decodable, Identifiable, Sendable {
    public let id: LayoutExampleID
    public let title: String
    public let summary: String
    public let applications: [String]
    public let windows: [LayoutExampleWindow]
    public let file: String
    public let sourceSHA256: String
    /// How many workspaces the layout arranges (contiguous from 1).
    public var workspaces: Int { windows.map(\.workspaceNumber).max() ?? 1 }
    enum CodingKeys: String, CodingKey { case id, title, summary, applications, windows, file; case sourceSHA256 = "sha256" }
}
/// Maintained descriptions/wireframes of the bundled, hash-admitted Lua files.
/// These are illustrations of intended geometry, never observed guest state.
public enum LayoutExamples {
    static let directory = "Resources/Provisioning/omarchy/examples/layouts"
    public static func catalogue() throws -> [LayoutExample] {
        _ = try SetupPlanner.engine()
        guard let url = Bundle.module.url(forResource: "catalogue", withExtension: "json", subdirectory: directory) else { throw ManifestError(.resource) }
        struct Catalogue: Decodable { let schema_version: Int; let examples: [LayoutExample] }
        let value = try JSONDecoder().decode(Catalogue.self, from: Data(contentsOf: url))
        guard value.schema_version == 1, value.examples.map(\.id) == LayoutExampleID.allCases else { throw ManifestError(.resource) }
        for example in value.examples {
            guard example.file == example.id.rawValue + ".lua", boundedText(example.title, bytes: 80), boundedText(example.summary, bytes: 200),
                  !example.applications.isEmpty, example.applications.count <= 8, example.applications.allSatisfy({ boundedText($0, bytes: 64) }),
                  (1...16).contains(example.windows.count),
                  Set(example.windows.map(\.workspaceNumber)) == Set(1...example.workspaces), example.workspaces <= 10 else { throw ManifestError(.resource) }
            guard let file = Bundle.module.url(forResource: example.id.rawValue, withExtension: "lua", subdirectory: directory),
                  let data = try? Data(contentsOf: file), !data.isEmpty, data.count <= 256 * 1024,
                  String(data: data, encoding: .utf8) != nil, digest(data) == example.sourceSHA256 else { throw ManifestError(.resource) }
            for window in example.windows {
                guard window.workspace.map({ (1...10).contains($0) }) ?? true, boundedText(window.label, bytes: 64), [window.x, window.y, window.width, window.height].allSatisfy(\.isFinite),
                      window.x >= 0, window.y >= 0, window.width > 0, window.height > 0,
                      window.x + window.width <= 1, window.y + window.height <= 1 else { throw ManifestError(.resource) }
            }
        }
        return value.examples
    }
    public static func source(_ id: LayoutExampleID) throws -> Data {
        _ = try catalogue()
        guard let url = Bundle.module.url(forResource: id.rawValue, withExtension: "lua", subdirectory: directory),
              let data = try? Data(contentsOf: url), !data.isEmpty, data.count <= 256 * 1024, String(data: data, encoding: .utf8) != nil else { throw ManifestError(.resource) }
        return data
    }
}
