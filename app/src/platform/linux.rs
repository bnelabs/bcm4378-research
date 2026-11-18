use crate::network::{
    Channel, Route, Snapshot, Wifi, clean_value, country_code, first_executable, read_command,
    valid_interface,
};
use serde::Deserialize;
use std::fs;
use std::net::Ipv4Addr;
use std::path::Path;

const IW: &[&str] = &["/usr/bin/iw", "/usr/sbin/iw", "/sbin/iw"];

#[derive(Deserialize)]
struct DefaultRoute {
    dev: Option<String>,
    gateway: Option<Ipv4Addr>,
    #[serde(default)]
    metric: u32,
}

fn route_from_json(text: &str) -> Route {
    serde_json::from_str::<Vec<DefaultRoute>>(text)
        .unwrap_or_default()
        .into_iter()
        .filter(|row| row.dev.as_deref().is_some_and(valid_interface))
        .min_by_key(|row| row.metric)
        .map_or_else(Route::default, |row| Route {
            interface: row.dev,
            router: row.gateway,
        })
}

fn managed_interfaces(text: &str) -> Vec<(String, Option<u32>)> {
    let mut phy = None;
    let mut interface = None;
    let mut rows = Vec::new();
    for line in text.lines().map(str::trim) {
        if let Some(id) = line.strip_prefix("phy#") {
            phy = id.parse().ok();
            interface = None;
        } else if let Some(name) = line.strip_prefix("Interface ") {
            interface = valid_interface(name).then(|| name.to_string());
        } else if line == "type managed" {
            if let Some(name) = interface.take() {
                rows.push((name, phy));
            }
        }
    }
    rows
}

fn primary_channel(text: &str) -> Option<Channel> {
    let line = text
        .lines()
        .map(str::trim)
        .find_map(|line| line.strip_prefix("channel "))?;
    let (number, rest) = line.split_once(" (")?;
    let (frequency, settings) = rest.split_once(" MHz)")?;
    let width = settings
        .split_once("width: ")
        .and_then(|(_, value)| value.split_whitespace().next()?.parse().ok());
    Channel::at(frequency.parse().ok()?, number.parse().ok(), width)
}

fn parse_frequencies(text: &str) -> Vec<Channel> {
    let mut channels: Vec<_> = text
        .lines()
        .filter_map(|line| {
            let (frequency, rest) = line.trim().strip_prefix("* ")?.split_once(" MHz [")?;
            let (number, flags) = rest.split_once(']')?;
            if flags.contains("(disabled)") {
                return None;
            }
            Channel::at(frequency.parse().ok()?, number.parse().ok(), Some(20))
        })
        .collect();
    channels.sort_unstable();
    channels.dedup();
    channels
}

fn country_for_phy(text: &str, phy: Option<u32>) -> Option<String> {
    let mut global = None;
    let mut active_phy = None;
    for line in text.lines().map(str::trim) {
        if let Some(id) = line.strip_prefix("phy#") {
            active_phy = id.split_whitespace().next()?.parse::<u32>().ok();
        } else if let Some(country) = line
            .strip_prefix("country ")
            .and_then(|line| line.split_once(':'))
        {
            let code = country_code(country.0).filter(|code| code != "00");
            if active_phy.is_none() {
                global = code;
            } else if active_phy == phy {
                return code.or(global);
            }
        }
    }
    global
}

fn read_link(text: &str, wifi: &mut Wifi) {
    let field = |name: &str| {
        text.lines()
            .map(str::trim)
            .find_map(|line| line.strip_prefix(name))
    };
    wifi.connected = text.lines().any(|line| line.starts_with("Connected to "));
    wifi.signal = field("signal:").and_then(|value| value.split_whitespace().next()?.parse().ok());
    wifi.rate = field("tx bitrate:")
        .and_then(|value| value.split_whitespace().next()?.parse::<f32>().ok())
        .filter(|rate| rate.is_finite() && *rate > 0.0);
    wifi.channel =
        field("freq:").and_then(|value| Channel::at(value.trim().parse().ok()?, None, None));
}

fn wireless_proc(interface: &str) -> Option<(i16, Option<i16>)> {
    let text = fs::read_to_string("/proc/net/wireless").ok()?;
    let values = text.lines().find_map(|line| {
        let (name, rest) = line.split_once(':')?;
        (name.trim() == interface).then_some(rest)
    })?;
    let mut values = values.split_whitespace().skip(2);
    let mut reading = || {
        values
            .next()?
            .trim_end_matches('.')
            .parse::<i16>()
            .ok()
            .filter(|value| (-125..=-1).contains(value))
    };
    Some((reading()?, reading()))
}

fn chip_for(interface: &str) -> Option<String> {
    let device = Path::new("/sys/class/net").join(interface).join("device");
    let vendor = fs::read_to_string(device.join("vendor")).ok()?;
    let part = fs::read_to_string(device.join("device")).ok()?;
    let vendor = u16::from_str_radix(vendor.trim().strip_prefix("0x")?, 16).ok()?;
    let part = u16::from_str_radix(part.trim().strip_prefix("0x")?, 16).ok()?;
    let name = match (vendor, part) {
        (0x14e4, 0x4425) => return Some("Broadcom BCM4378".into()),
        (0x14e4, _) => "Broadcom",
        (0x8086, _) => "Intel",
        (0x168c | 0x17cb, _) => "Qualcomm",
        (0x14c3, _) => "MediaTek",
        (0x10ec, _) => "Realtek",
        _ => "PCI",
    };
    Some(format!("{name} {vendor:04x}:{part:04x}"))
}

pub fn snapshot(include_channels: bool) -> Snapshot {
    let route = first_executable(&["/usr/bin/ip", "/usr/sbin/ip", "/sbin/ip"])
        .and_then(|ip| read_command(ip, &["-j", "-4", "route", "show", "default"]))
        .map_or_else(Route::default, |text| route_from_json(&text));
    let iw = first_executable(IW);
    let rows = iw
        .and_then(|tool| read_command(tool, &["dev"]))
        .map_or_else(Vec::new, |text| managed_interfaces(&text));
    let fallback = fs::read_dir("/sys/class/net")
        .ok()
        .into_iter()
        .flatten()
        .flatten()
        .find_map(|entry| {
            let name = entry.file_name().into_string().ok()?;
            (valid_interface(&name)
                && (entry.path().join("wireless").is_dir()
                    || entry.path().join("phy80211").exists()))
            .then_some((name, None))
        });
    let routed = route.interface.as_deref().filter(|name| {
        Path::new("/sys/class/net")
            .join(name)
            .join("wireless")
            .is_dir()
            || rows.iter().any(|(interface, _)| interface == name)
    });
    let selected = routed
        .and_then(|name| {
            rows.iter()
                .find(|(interface, _)| interface == name)
                .cloned()
                .or_else(|| Some((name.to_string(), None)))
        })
        .or_else(|| rows.into_iter().next())
        .or(fallback);
    let Some((interface, phy)) = selected else {
        let note = if iw.is_none() {
            "Install iw so KYW can read the Wi-Fi adapter."
        } else {
            "Linux didn’t report a Wi-Fi adapter."
        };
        return Snapshot {
            route,
            note: Some(note),
            ..Snapshot::default()
        };
    };
    let mut wifi = Wifi {
        interface: interface.clone(),
        chip: chip_for(&interface),
        ..Wifi::default()
    };
    if let Some(text) = iw.and_then(|tool| read_command(tool, &["dev", &interface, "link"])) {
        read_link(&text, &mut wifi);
    } else if let Some((signal, noise)) = wireless_proc(&interface) {
        wifi.signal = Some(signal);
        wifi.noise = noise;
        wifi.connected = routed.is_some();
    }
    let mut channels = Vec::new();
    if let Some(tool) = iw {
        if wifi.connected {
            wifi.channel = read_command(tool, &["dev", &interface, "info"])
                .and_then(|text| primary_channel(&text))
                .or(wifi.channel);
        }
        if include_channels {
            wifi.country =
                read_command(tool, &["reg", "get"]).and_then(|text| country_for_phy(&text, phy));
            if let Some(phy) = phy {
                channels = read_command(tool, &["phy", &format!("phy{phy}"), "info"])
                    .map_or_else(Vec::new, |text| parse_frequencies(&text));
            }
        }
    }
    if include_channels {
        let device = Path::new("/sys/class/net").join(&interface).join("device");
        wifi.driver = fs::read_link(device.join("driver"))
            .ok()
            .and_then(|link| clean_value(link.file_name()?.to_str()?));
        if let Some(output) =
            first_executable(&["/usr/bin/ethtool", "/usr/sbin/ethtool", "/sbin/ethtool"])
                .and_then(|tool| read_command(tool, &["-i", &interface]))
        {
            wifi.firmware = output
                .lines()
                .find_map(|line| line.strip_prefix("firmware-version:").and_then(clean_value));
        }
    }
    Snapshot {
        wifi: Some(wifi),
        route,
        channels,
        radio_control: None,
        note: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn managed_radio_and_channel_are_selected() {
        let devices = "phy#12\n\tInterface p2p-dev-wlan0\n\t\ttype P2P-device\n\tInterface wlan0\n\t\ttype managed\n";
        assert_eq!(
            managed_interfaces(devices),
            vec![("wlan0".into(), Some(12))]
        );
        let channel =
            primary_channel("  channel 40 (5200 MHz), width: 80 MHz, center1: 5210 MHz\n").unwrap();
        assert_eq!((channel.number, channel.width), (40, Some(80)));
        assert_eq!(
            parse_frequencies("* 5180 MHz [36] (20.0 dBm)\n* 5720 MHz [144] (disabled)").len(),
            1
        );
        assert_eq!(
            country_for_phy(
                "global\ncountry 00: DFS-UNSET\nphy#12 (self-managed)\ncountry TR: DFS-ETSI",
                Some(12)
            )
            .as_deref(),
            Some("TR")
        );
    }

    #[test]
    fn default_route_metric_and_link_parse() {
        let route = route_from_json(
            r#"[{"dev":"enp0s1","metric":900},{"dev":"wlan0","metric":600,"gateway":"192.0.2.1"}]"#,
        );
        assert_eq!(route.interface.as_deref(), Some("wlan0"));
        let mut wifi = Wifi::default();
        read_link(
            "Connected to 00:11:22:33:44:55\n\tsignal: -58 dBm\n\tfreq: 5200\n\ttx bitrate: 612.5 MBit/s",
            &mut wifi,
        );
        assert!(wifi.connected);
        assert_eq!(wifi.signal, Some(-58));
        assert_eq!(wifi.rate, Some(612.5));
    }
}
