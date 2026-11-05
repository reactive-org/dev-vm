import Darwin
import Foundation

/// Docker resource names derive only from a new job UUID. Never decode commands,
/// mounts, names, endpoints or deletion targets from an artifact or user manifest.
public struct FactoryBuildEngine: Sendable {
    public let docker: FactoryDockerClient
    public let recipe: FactoryRecipe
    public let downloader: any FactoryBuildDownloading
    public init(docker: FactoryDockerClient, recipe: FactoryRecipe, downloader: any FactoryBuildDownloading = FactoryBuildDownloader()) {
        self.docker = docker; self.recipe = recipe; self.downloader = downloader
    }
    public func build(_ plan: FactoryBuildPlan, jobID: UUID, root: URL, admission: FactoryDockerAdmission,
                      output: FactoryBuildOutput, stage: @escaping @Sendable (FactoryBuildStage) async throws -> Void) async throws -> URL {
        _ = try FactoryBuildPlan(name: plan.name, sizeGiB: plan.sizeGiB)
        guard plan.recipeSHA256 == recipe.identity else { throw FactoryBuildFailure.inputsChanged }
        try recipe.verify()
        let workspace = root.appendingPathComponent(jobID.uuidString)
        try factoryDirectory(root); try factoryDirectory(workspace)
        let input = workspace.appendingPathComponent("input"), downloads = root.appendingPathComponent("Downloads"), cache = root.appendingPathComponent("Packages")
        try factoryDirectory(input, create: true); try factoryDirectory(downloads, create: true); try factoryDirectory(cache, create: true)
        for name in ["output", "factory-work"] { try factoryDirectory(workspace.appendingPathComponent(name), create: true) }
        let token = jobID.uuidString.lowercased(), volume = "omarchy-factory-" + token, container = "omarchy-factory-" + token
        let emit: @Sendable (Data) -> Void = { output.append($0) }
        let work: Result<URL, any Error>
        do {
            try await stage(.preparing)
            let untar = try await docker.runner.run(.init(executable: URL(fileURLWithPath: "/usr/bin/tar"), arguments: ["-xzf", recipe.archive.path, "-C", input.path], directory: workspace, environment: ["PATH": "/usr/bin:/bin", "LC_ALL": "C"], timeoutSeconds: 60), output: emit)
            guard untar.status == 0 else { throw FactoryBuildFailure.inputsChanged }
            try recipe.verifyStaged(input)
            try await stage(.downloading)
            for download in recipe.downloads {
                try Task.checkCancellation()
                let file = downloads.appendingPathComponent(download.name)
                if !FileManager.default.fileExists(atPath: file.path) { try await downloader.download(download, to: file) }
                guard try factoryFileHash(file) == download.sha256 else { throw FactoryBuildFailure.downloadFailed }
                emit(Data(("Verified build input: " + download.name + "\r\n").utf8))
            }
            try await stage(.packages)
            let upstream = input.appendingPathComponent("upstream"), imageFile = workspace.appendingPathComponent("builder.id")
            _ = try await docker.run(admission, ["build", "--platform", "linux/arm64", "--iidfile", imageFile.path,
                "--label", "dev.omarchy.factory-build=" + token, "-f", upstream.appendingPathComponent("guest/factory/Containerfile").path, upstream.path], directory: workspace, timeout: 3600, stream: true, output: emit)
            let imageID = try String(contentsOf: imageFile, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
            guard matches(imageID, "sha256:[a-f0-9]{64}") else { throw FactoryBuildFailure.invalidArtifact }
            try recipe.verifyStaged(input)
            guard try await names(admission, type: "container", name: container).isEmpty,
                  try await names(admission, type: "volume", name: volume).isEmpty else { throw FactoryBuildFailure.cleanupRequired }
            _ = try await docker.run(admission, ["volume", "create", "--label", "dev.omarchy.factory-build=" + token, volume], directory: workspace)
            try await stage(.image)
            var args = ["run", "--name", container, "--label", "dev.omarchy.factory-build=" + token, "--platform", "linux/arm64", "--privileged"]
            for (source, destination, readOnly) in [(upstream.path, "/workspace", true), (input.appendingPathComponent("profile").path, "/input-profile", true), (downloads.path, "/downloads", true), (workspace.appendingPathComponent("factory-work").path, "/factory-work", false), (cache.path, "/factory-work/pacman-cache", false), (workspace.appendingPathComponent("output").path, "/output", false)] {
                guard !source.contains(",") else { throw FactoryBuildFailure.invalidRequest }
                args += ["--mount", "type=bind,src=" + source + ",dst=" + destination + (readOnly ? ",readonly" : "")]
            }
            args += ["--mount", "type=volume,src=" + volume + ",dst=/work", "--entrypoint", "/bin/bash", imageID, "/input-profile/build-container.sh", "build", String(plan.sizeGiB)]
            _ = try await docker.run(admission, args, directory: workspace, timeout: 14400, stream: true, output: emit)
            try await stage(.verifying)
            let result = workspace.appendingPathComponent("output")
            try recipe.buildEvidence(plan: plan, imageID: imageID).write(to: result.appendingPathComponent("image-build.json"), options: .withoutOverwriting)
            // Manager-side bundle preparation and independent admission follow;
            // successful Docker exit alone never publishes a factory.
            work = .success(result)
        } catch { work = .failure(error) }
        let cleanup = await Task.detached { () -> Bool in
            do { try await self.cleanup(jobID: jobID, admission: admission); return true } catch { return false }
        }.value
        guard cleanup else { throw FactoryBuildFailure.cleanupRequired }
        return try work.get()
    }
    func names(_ admission: FactoryDockerAdmission, type: String, name: String) async throws -> [String] {
        let args = type == "container" ? ["container", "ls", "--all", "--filter", "name=^/" + name + "$", "--format", "{{json .Names}}"] : ["volume", "ls", "--filter", "name=^" + name + "$", "--format", "{{json .Name}}"]
        let data = try await docker.run(admission, args, directory: docker.home)
        let values = try data.split(separator: 10).map { line -> String in
            guard case .string(let value) = try PlainDataParser.parse(Data(line), format: .json), value == name else { throw FactoryBuildFailure.cleanupRequired }; return value
        }
        guard values.count <= 1 else { throw FactoryBuildFailure.cleanupRequired }; return values
    }
    public func cleanup(jobID: UUID, admission: FactoryDockerAdmission) async throws {
        let token = jobID.uuidString.lowercased(), name = "omarchy-factory-" + token
        for type in ["container", "volume"] {
            if try await names(admission, type: type, name: name).isEmpty { continue }
            let format = type == "container" ? "{\"id\":{{json .Id}},\"labels\":{{json .Config.Labels}}}" : "{\"id\":{{json .Name}},\"labels\":{{json .Labels}}}"
            let data = try await docker.run(admission, [type, "inspect", "--format", format, name], directory: docker.home)
            guard case .object(let doc) = try PlainDataParser.parse(data, format: .json), case .object(let labels) = doc["labels"], labels["dev.omarchy.factory-build"] == .string(token),
                  case .string(let id) = doc["id"], type == "container" ? matches(id, "[a-f0-9]{64}") : id == name else { throw FactoryBuildFailure.cleanupRequired }
            _ = try await docker.run(admission, [type, "rm"] + (type == "container" ? ["--force"] : []) + [id], directory: docker.home)
            guard try await names(admission, type: type, name: name).isEmpty else { throw FactoryBuildFailure.cleanupRequired }
        }
    }
}
func factoryDirectory(_ directory: URL, create: Bool = false) throws {
    if create, mkdir(directory.path, 0o700) != 0, errno != EEXIST { throw FactoryBuildFailure.invalidRequest }
    var s = stat()
    guard lstat(directory.path, &s) == 0, s.st_mode & S_IFMT == S_IFDIR, s.st_uid == getuid(), s.st_mode & 0o7777 == 0o700,
          directory.path == directory.resolvingSymlinksInPath().path else { throw FactoryBuildFailure.invalidRequest }
}
