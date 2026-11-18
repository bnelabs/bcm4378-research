fn main() {
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("macos") {
        return;
    }
    println!("cargo:rerun-if-changed=src/platform/macos.m");
    cc::Build::new()
        .file("src/platform/macos.m")
        .flag("-fobjc-arc")
        .compile("kyw_macos");
    for framework in [
        "Foundation",
        "AppKit",
        "CoreWLAN",
        "IOKit",
        "SystemConfiguration",
    ] {
        println!("cargo:rustc-link-lib=framework={framework}");
    }
}
