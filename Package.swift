// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "DevVMProvisioning",
    platforms: [.macOS(.v15)],
    products: [
        .library(name: "DevVMProvisioningCore", targets: ["DevVMProvisioningCore"]),
        .executable(name: "dev-vm", targets: ["dev-vm"])
    ],
    targets: [
        .target(name: "CDevVMYAML", cSettings: [.define("YAML_DECLARE_STATIC")]),
        .target(name: "DevVMProvisioningCore", dependencies: ["CDevVMYAML"],
                resources: [.copy("Resources")]),
        .executableTarget(name: "dev-vm", dependencies: ["DevVMProvisioningCore"]),
        .testTarget(name: "DevVMProvisioningCoreTests", dependencies: ["DevVMProvisioningCore"],
                    path: "tests/DevVMProvisioningCoreTests",
                    resources: [.copy("Fixtures")])
    ],
    swiftLanguageModes: [.v6]
)
