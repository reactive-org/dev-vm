// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "DevVMProvisioning",
    platforms: [.macOS(.v15)],
    products: [
        .library(name: "DevVMProvisioningCore", targets: ["DevVMProvisioningCore"]),
        .executable(name: "dev-vm", targets: ["dev-vm"])
    ],
    dependencies: [.package(url: "https://github.com/dduan/TOMLDecoder.git", revision: "a2bbd2796fe3064e107de18cb56031052c4fa899")],
    targets: [
        .target(name: "CDevVMYAML", cSettings: [.define("YAML_DECLARE_STATIC")]),
        .target(name: "DevVMProvisioningCore", dependencies: ["CDevVMYAML", .product(name: "TOMLDecoder", package: "TOMLDecoder")],
                resources: [.copy("Resources")]),
        .executableTarget(name: "dev-vm", dependencies: ["DevVMProvisioningCore"]),
        .testTarget(name: "DevVMProvisioningCoreTests", dependencies: ["DevVMProvisioningCore"],
                    path: "tests/DevVMProvisioningCoreTests",
                    resources: [.copy("Fixtures")])
    ],
    swiftLanguageModes: [.v6]
)
