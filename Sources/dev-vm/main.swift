import DevVMProvisioningCore
import Foundation

// Migration surface only. Legacy Python make entry points retain their current behavior.
let args = Array(CommandLine.arguments.dropFirst())
if args == ["--help"] || args == ["-h"] {
    print("Usage: dev-vm validate-manifest <manifest.json|manifest.yml|manifest.yaml>")
    print("Structure validation only; no resolution, asset capture, tool probes or VM operations.")
} else if args.count == 2, args[0] == "validate-manifest" {
    do {
        let manifest = try SetupManifest.read(URL(fileURLWithPath: args[1]))
        // Do not echo manifest values, paths, variables or custom task contents.
        print("{\"api_version\":1,\"schema_version\":1,\"structure_valid\":true,\"resolved\":false,\"execution_available\":false,\"dotfiles\":\(manifest.dotfiles.count),\"tasks\":\(manifest.tasks.count),\"assets\":\(manifest.assets.count)}")
    } catch {
        let message = (error as? ManifestError)?.description ?? "manifest.file"
        FileHandle.standardError.write(Data((message + "\n").utf8))
        exit(1)
    }
} else {
    FileHandle.standardError.write(Data("Usage: dev-vm validate-manifest <manifest.json|manifest.yml|manifest.yaml>\n".utf8))
    exit(2)
}
