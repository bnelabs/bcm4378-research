#[cfg(not(target_os = "macos"))]
use crate::network::RadioChange;

#[cfg(any(target_os = "freebsd", target_os = "openbsd"))]
mod bsd;
#[cfg(any(target_os = "freebsd", target_os = "openbsd"))]
pub use bsd::snapshot;

#[cfg(target_os = "linux")]
mod linux;
#[cfg(target_os = "linux")]
pub use linux::snapshot;

#[cfg(target_os = "macos")]
mod macos;
#[cfg(target_os = "macos")]
pub use macos::{change_radio, choose_file, snapshot};

#[cfg(not(target_os = "macos"))]
pub fn chooser() -> Option<&'static str> {
    crate::network::first_executable(&["/usr/bin/zenity", "/usr/local/bin/zenity"])
}

#[cfg(not(target_os = "macos"))]
pub fn change_radio(change: RadioChange) -> Result<(), &'static str> {
    match change {
        RadioChange::Power(_) => Err("Use your system’s Wi-Fi settings to change radio power."),
        RadioChange::Channel(_) => Err("Use your router’s Wi-Fi settings to change its channel."),
    }
}

pub fn name() -> &'static str {
    match std::env::consts::OS {
        "macos" => "macOS",
        "linux" => "Linux",
        "freebsd" => "FreeBSD",
        "openbsd" => "OpenBSD",
        _ => "This system",
    }
}
