use crate::network::{
    Band, RadioAvailability, RadioChange, Snapshot, Wifi, WireChannel, clean_value, country_code,
    parse_bsd_route, read_command, valid_interface,
};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::ffi::{CStr, c_char, c_int};
use std::fs;
use std::io::Read;
use std::path::PathBuf;
use std::path::{Component, Path};

unsafe extern "C" {
    fn kyw_mac_read(include_channels: c_int) -> *mut c_char;
    fn kyw_mac_change(power: c_int, band: c_int, number: c_int, width: c_int) -> c_int;
    fn kyw_mac_choose_file() -> *mut c_char;
}

pub fn choose_file() -> Option<PathBuf> {
    // AppKit file panels must be opened on the GUI thread.
    let raw = unsafe { kyw_mac_choose_file() };
    if raw.is_null() {
        return None;
    }
    let path = unsafe { CStr::from_ptr(raw).to_str().ok().map(PathBuf::from) };
    unsafe { libc::free(raw.cast()) };
    path
}

#[derive(Deserialize)]
struct MacStatus {
    interface: String,
    connected: bool,
    powered: bool,
    channel: Option<WireChannel>,
    signal: Option<i16>,
    noise: Option<i16>,
    rate: Option<f32>,
    country: Option<String>,
    chip_number: Option<u16>,
    firmware_line: Option<String>,
    image: Option<String>,
    #[serde(default)]
    channels: Vec<WireChannel>,
    #[serde(default)]
    wired: Vec<String>,
}

fn open_status(include_channels: bool) -> Option<MacStatus> {
    // The shim returns an owned UTF-8 string allocated by strdup.
    let raw = unsafe { kyw_mac_read(i32::from(include_channels)) };
    if raw.is_null() {
        return None;
    }
    let value = unsafe { serde_json::from_slice(CStr::from_ptr(raw).to_bytes()).ok() };
    unsafe { libc::free(raw.cast()) };
    value
}

pub fn snapshot(include_channels: bool) -> Snapshot {
    let route = read_command("/sbin/route", &["-n", "get", "-inet", "default"])
        .map_or_else(Default::default, |value| parse_bsd_route(&value));
    let Some(status) = open_status(include_channels) else {
        return Snapshot {
            route,
            note: Some("macOS didn’t report a Wi-Fi adapter."),
            ..Snapshot::default()
        };
    };

    let radio_control = include_channels.then(|| radio_availability(&status));
    let mut channels: Vec<_> = status
        .channels
        .into_iter()
        .filter_map(WireChannel::into_channel)
        .collect();
    channels.sort_unstable();
    channels.dedup();
    let wifi = Wifi {
        interface: status.interface,
        connected: status.connected,
        channel: status.channel.and_then(WireChannel::into_channel),
        signal: status.signal,
        noise: status.noise,
        rate: status.rate,
        country: status.country.as_deref().and_then(country_code),
        chip: status.chip_number.map(|part| format!("Broadcom BCM{part}")),
        firmware: status.firmware_line.as_deref().and_then(firmware_version),
        rtos: status.image.as_deref().and_then(rtos_for_stock_image),
        powered: Some(status.powered),
        ..Wifi::default()
    };
    Snapshot {
        wifi: Some(wifi),
        route,
        channels,
        radio_control,
        note: None,
    }
}

fn firmware_version(line: &str) -> Option<String> {
    let first = line.split_once("version ")?.1.split_whitespace().next()?;
    if !first
        .bytes()
        .all(|byte| byte.is_ascii_digit() || byte == b'.')
    {
        return None;
    }
    clean_value(first)
}

fn rtos_for_stock_image(relative: &str) -> Option<&'static str> {
    let path = Path::new(relative);
    if path.extension()? != "trx"
        || !path
            .components()
            .all(|part| matches!(part, Component::Normal(_)))
    {
        return None;
    }
    let root = fs::canonicalize("/usr/share/firmware/wifi").ok()?;
    let real = root.join(path).canonicalize().ok()?;
    if !real.starts_with(&root) {
        return None;
    }
    let file = fs::File::open(real).ok()?;
    let metadata = file.metadata().ok()?;
    if !metadata.is_file() || !(1..=4 * 1024 * 1024).contains(&metadata.len()) {
        return None;
    }
    let mut bytes = Vec::with_capacity(metadata.len() as usize);
    file.take(metadata.len() + 1).read_to_end(&mut bytes).ok()?;
    if bytes.len() as u64 != metadata.len() {
        return None;
    }
    let digest = format!("{:x}", Sha256::digest(&bytes));
    match digest.as_str() {
        "7230e9ea5a3ac10c9ba5ea9093f678ae813b0423bbf1f37f7c38ca12eebb1e06"
        | "c06572025af27c6dbd465dad5bdc0a26ca1b2b01a7a06d9899d5a947642dc8a6"
        | "ce0ffa9df958a589a8de93374e71034dc6572ef9e292e032eefa93ba45a6bb3a" => Some("ThreadX 5.6"),
        _ => None,
    }
}

fn unscoped_defaults(text: &str) -> Option<Vec<&str>> {
    let header: Vec<_> = text
        .lines()
        .find(|line| line.starts_with("Destination"))?
        .split_whitespace()
        .collect();
    let flags = header.iter().position(|column| *column == "Flags")?;
    let device = header.iter().position(|column| *column == "Netif")?;
    let mut defaults = Vec::new();
    for line in text.lines() {
        let fields: Vec<_> = line.split_whitespace().collect();
        if fields.first() != Some(&"default") {
            continue;
        }
        if !fields.get(flags)?.contains('I') {
            let interface = *fields.get(device)?;
            if !valid_interface(interface) {
                return None;
            }
            defaults.push(interface);
        }
    }
    Some(defaults)
}

fn has_wired_route(status: &MacStatus) -> bool {
    let mut found = false;
    for family in ["inet", "inet6"] {
        let Some(table) = read_command("/usr/sbin/netstat", &["-rn", "-f", family]) else {
            return false;
        };
        let Some(defaults) = unscoped_defaults(&table) else {
            return false;
        };
        for interface in defaults {
            if interface == status.interface || !status.wired.iter().any(|name| name == interface) {
                return false;
            }
            found = true;
        }
    }
    found
}

fn radio_availability(status: &MacStatus) -> RadioAvailability {
    if status.connected {
        RadioAvailability {
            enabled: false,
            reason: "The radio is in use. Disconnect Wi-Fi on a wired test Mac to change it here.",
        }
    } else if has_wired_route(status) {
        RadioAvailability {
            enabled: true,
            reason: "Wi-Fi is idle and this Mac has a verified Ethernet route.",
        }
    } else {
        RadioAvailability {
            enabled: false,
            reason: "An active Ethernet route is required before changing this radio.",
        }
    }
}

pub fn change_radio(change: RadioChange) -> Result<(), &'static str> {
    let status = open_status(true).ok_or("macOS didn’t report a Wi-Fi adapter.")?;
    let permission = radio_availability(&status);
    if !permission.enabled {
        return Err(permission.reason);
    }
    let code = match change {
        RadioChange::Power(value) => unsafe { kyw_mac_change(i32::from(value), 0, 0, 0) },
        RadioChange::Channel(channel) => {
            let band = match channel.band {
                Band::Two => 2,
                Band::Five => 5,
                Band::Six => 6,
            };
            let width = channel.width.ok_or("The selected channel has no width.")?;
            unsafe { kyw_mac_change(-1, band, i32::from(channel.number), i32::from(width)) }
        }
    };
    match code {
        0 => Ok(()),
        1 => Err("The radio became busy before it could change."),
        3 => Err("macOS no longer offers that channel."),
        _ => Err("macOS didn’t apply the setting. Check Wi-Fi in System Settings."),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_versions_without_board_labels_or_paths() {
        assert_eq!(
            firmware_version("wl0: Aug 1 version 18.20.10 FWID 01-abc").as_deref(),
            Some("18.20.10")
        );
        assert!(firmware_version("version /Users/private").is_none());
    }

    #[test]
    fn route_parser_separates_scoped_entries() {
        let routes = "Destination Gateway Flags Netif Expire\ndefault 192.0.2.1 UG en7\ndefault fe80::%en3 UGcI en3\n";
        assert_eq!(unscoped_defaults(routes), Some(vec!["en7"]));
        assert!(unscoped_defaults("default something").is_none());
    }
}
