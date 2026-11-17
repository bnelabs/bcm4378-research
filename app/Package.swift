// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "KnowYourWifi",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "KYW", targets: ["KYW"])],
    targets: [.executableTarget(name: "KYW")]
)
