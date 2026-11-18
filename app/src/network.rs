use serde::Deserialize;
use std::io::Read;
use std::net::Ipv4Addr;
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub enum Band {
    Two,
    Five,
    Six,
}

impl Band {
    pub const ALL: [Self; 3] = [Self::Two, Self::Five, Self::Six];

    pub fn label(self) -> &'static str {
        match self {
            Self::Two => "2.4 GHz",
            Self::Five => "5 GHz",
            Self::Six => "6 GHz",
        }
    }

    pub fn from_mhz(frequency: u16) -> Option<Self> {
        match frequency {
            2400..=2500 => Some(Self::Two),
            4900..=5924 => Some(Self::Five),
            5925..=7125 => Some(Self::Six),
            _ => None,
        }
    }

    pub fn mhz(self, number: u16) -> u16 {
        match (self, number) {
            (Self::Two, 14) => 2484,
            (Self::Two, _) => 2407 + 5 * number,
            (Self::Five, 182..=196) => 4000 + 5 * number,
            (Self::Five, _) => 5000 + 5 * number,
            (Self::Six, 2) => 5935,
            (Self::Six, _) => 5950 + 5 * number,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct Channel {
    pub band: Band,
    pub number: u16,
    pub frequency: u16,
    pub width: Option<u16>,
}

impl Channel {
    pub fn at(frequency: u16, number: Option<u16>, width: Option<u16>) -> Option<Self> {
        let band = Band::from_mhz(frequency)?;
        let number = number.or_else(|| (1..=233).find(|&n| band.mhz(n) == frequency))?;
        Some(Self {
            band,
            number,
            frequency,
            width,
        })
    }

    pub fn new(band: Band, number: u16, width: Option<u16>) -> Option<Self> {
        if !(1..=233).contains(&number) {
            return None;
        }
        Self::at(band.mhz(number), Some(number), width)
    }
}

#[derive(Clone, Default)]
pub struct Wifi {
    pub interface: String,
    pub connected: bool,
    pub channel: Option<Channel>,
    pub signal: Option<i16>,
    pub signal_percent: Option<u8>,
    pub noise: Option<i16>,
    pub rate: Option<f32>,
    pub country: Option<String>,
    pub chip: Option<String>,
    pub firmware: Option<String>,
    pub rtos: Option<&'static str>,
    pub driver: Option<String>,
    pub powered: Option<bool>,
}

#[derive(Clone, Default, Eq, PartialEq)]
pub struct Route {
    pub interface: Option<String>,
    pub router: Option<Ipv4Addr>,
}

#[derive(Default)]
pub struct Snapshot {
    pub wifi: Option<Wifi>,
    pub route: Route,
    pub channels: Vec<Channel>,
    pub radio_control: Option<RadioAvailability>,
    pub note: Option<&'static str>,
}

#[derive(Clone, Copy)]
pub struct RadioAvailability {
    pub enabled: bool,
    pub reason: &'static str,
}

#[derive(Clone, Copy)]
pub enum RadioChange {
    Power(bool),
    Channel(Channel),
}

impl Snapshot {
    pub fn uses_wifi_for_ipv4(&self) -> bool {
        self.wifi.as_ref().is_some_and(|wifi| {
            wifi.connected && self.route.interface.as_deref() == Some(wifi.interface.as_str())
        })
    }

    pub fn can_check_router(&self) -> bool {
        self.uses_wifi_for_ipv4() && self.route.router.is_some()
    }
}

pub struct RouterCheck {
    pub times_ms: Vec<f32>,
}

impl RouterCheck {
    pub const TOTAL: usize = 4;

    pub fn median(&self) -> Option<f32> {
        let mut values = self.times_ms.clone();
        if values.is_empty() {
            return None;
        }
        values.sort_by(f32::total_cmp);
        let upper = values.len() / 2;
        let lower = (values.len() - 1) / 2;
        Some((values[lower] + values[upper]) / 2.0)
    }
}

pub fn check_router(expected: &Route) -> Result<RouterCheck, &'static str> {
    let before = crate::platform::snapshot(false);
    if !before.can_check_router() || &before.route != expected {
        return Err("Your route changed. Refresh the connection and try again.");
    }
    let router = expected
        .router
        .ok_or("The router address is unavailable.")?;
    let executable = match std::env::consts::OS {
        "linux" => first_executable(&["/usr/bin/ping", "/bin/ping"]),
        _ => first_executable(&["/sbin/ping", "/bin/ping", "/usr/sbin/ping"]),
    }
    .ok_or("The system’s ping tool is unavailable.")?;
    let destination = router.to_string();
    let output = command(
        executable,
        &["-n", "-c", "4", &destination],
        Duration::from_secs(9),
    )
    .ok_or("KYW couldn’t start the router check.")?;
    let after = crate::platform::snapshot(false);
    if !after.can_check_router() || &after.route != expected {
        return Err("Your route changed during the check. Run it again on a steady connection.");
    }
    let times_ms = output
        .text
        .lines()
        .filter_map(|line| {
            let (_, time) = line.split_once("time=")?;
            let value: f32 = time.split_whitespace().next()?.parse().ok()?;
            (value.is_finite() && value >= 0.0).then_some(value)
        })
        .take(RouterCheck::TOTAL)
        .collect();
    Ok(RouterCheck { times_ms })
}

pub(crate) fn parse_bsd_route(text: &str) -> Route {
    let mut result = Route::default();
    for line in text.lines() {
        if let Some((key, value)) = line.trim().split_once(':') {
            match key {
                "interface" if valid_interface(value.trim()) => {
                    result.interface = Some(value.trim().to_string());
                }
                "gateway" => result.router = value.trim().parse().ok(),
                _ => {}
            }
        }
    }
    result
}

pub(crate) fn valid_interface(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 32
        && name.as_bytes()[0].is_ascii_alphanumeric()
        && name
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"._-".contains(&b))
}

pub(crate) fn country_code(value: &str) -> Option<String> {
    let code = value.trim();
    (code.len() == 2 && code.bytes().all(|b| b.is_ascii_alphanumeric()))
        .then(|| code.to_ascii_uppercase())
}

pub(crate) fn clean_value(value: &str) -> Option<String> {
    let value = value.trim();
    (!value.is_empty()
        && value.chars().count() <= 140
        && !value.contains(['/', '\\'])
        && !value.chars().any(char::is_control))
    .then(|| value.to_string())
}

pub(crate) fn first_executable<'a>(choices: &[&'a str]) -> Option<&'a str> {
    choices
        .iter()
        .copied()
        .find(|path| std::path::Path::new(path).is_file())
}

pub(crate) fn read_command(path: &str, args: &[&str]) -> Option<String> {
    let output = command(path, args, Duration::from_secs(3))?;
    output.success.then_some(output.text)
}

pub(crate) struct CommandOutput {
    pub text: String,
    pub success: bool,
}

pub(crate) fn command(path: &str, args: &[&str], timeout: Duration) -> Option<CommandOutput> {
    let mut child = Command::new(path)
        .args(args)
        .env("LC_ALL", "C")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .ok()?;
    let stdout = child.stdout.take()?;
    let reader = thread::spawn(move || {
        let mut output = Vec::new();
        stdout.take(2 * 1024 * 1024).read_to_end(&mut output).ok()?;
        Some(String::from_utf8_lossy(&output).into_owned())
    });
    let start = Instant::now();
    let success = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status.success(),
            Ok(None) if start.elapsed() < timeout => thread::sleep(Duration::from_millis(15)),
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                break false;
            }
        }
    };
    Some(CommandOutput {
        text: reader.join().ok()??,
        success,
    })
}

#[derive(Deserialize)]
pub struct WireChannel {
    pub band: u8,
    pub number: u16,
    pub width: Option<u16>,
}

impl WireChannel {
    pub fn into_channel(self) -> Option<Channel> {
        let band = match self.band {
            2 => Band::Two,
            5 => Band::Five,
            6 => Band::Six,
            _ => return None,
        };
        Channel::new(band, self.number, self.width)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frequencies_preserve_band_and_primary() {
        assert_eq!(Channel::at(5720, None, Some(20)).unwrap().number, 144);
        assert_eq!(Channel::at(5935, None, Some(20)).unwrap().number, 2);
        assert_eq!(Channel::at(2484, None, Some(20)).unwrap().number, 14);
        assert!(Channel::new(Band::Five, 0, None).is_none());
    }

    #[test]
    fn hides_paths_and_distinguishes_wifi_routes() {
        assert!(clean_value("/Users/someone/private-file").is_none());
        let mut snapshot = Snapshot {
            wifi: Some(Wifi {
                interface: "en0".into(),
                connected: true,
                ..Wifi::default()
            }),
            route: parse_bsd_route("interface: en7\ngateway: 192.0.2.1"),
            ..Snapshot::default()
        };
        assert!(!snapshot.can_check_router());
        snapshot.route = parse_bsd_route("interface: en0\ngateway: 192.0.2.1");
        assert!(snapshot.can_check_router());
    }
}
