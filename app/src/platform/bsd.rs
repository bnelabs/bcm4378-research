use crate::network::{
    Band, Channel, Snapshot, Wifi, country_code, parse_bsd_route, read_command, valid_interface,
};

fn words_after<'a>(text: &'a str, token: &str) -> Option<impl Iterator<Item = &'a str>> {
    let mut words = text.split_whitespace();
    words.find(|word| *word == token)?;
    Some(words)
}

fn wireless_blocks(text: &str) -> impl Iterator<Item = (&str, &str)> {
    text.split_inclusive('\n')
        .filter(|line| !line.starts_with(char::is_whitespace))
        .filter_map(|line| {
            let name = line.split_once(':')?.0;
            let start = line.as_ptr() as usize - text.as_ptr() as usize;
            let rest = &text[start + line.len()..];
            let rest_end = rest
                .split_inclusive('\n')
                .take_while(|row| row.starts_with(char::is_whitespace))
                .map(str::len)
                .sum::<usize>();
            (valid_interface(name)
                && (rest[..rest_end].contains("ieee80211:")
                    || rest[..rest_end].contains("\tssid ")))
            .then_some((name, &rest[..rest_end]))
        })
}

fn parse_wifi(interface: &str, block: &str) -> Wifi {
    let connected = block
        .lines()
        .map(str::trim)
        .any(|line| ["status: associated", "status: active"].contains(&line));
    let mut wifi = Wifi {
        interface: interface.into(),
        connected,
        ..Wifi::default()
    };
    let description = block
        .lines()
        .map(str::trim)
        .find(|line| line.starts_with("ieee80211:") || line.starts_with("ssid "));
    if let Some(description) = description {
        if let Some(mut after) =
            words_after(description, "channel").or_else(|| words_after(description, "chan"))
        {
            let number = after.next().and_then(|value| value.parse::<u16>().ok());
            if let (Some(n), Some(frequency)) = (
                number,
                after
                    .next()
                    .and_then(|value| value.trim_start_matches('(').parse::<u16>().ok()),
            ) {
                wifi.channel = Channel::at(frequency, Some(n), None);
            } else if let Some(n) = number {
                // OpenBSD does not always show MHz. The legacy bands have disjoint primary channel numbers.
                wifi.channel = Channel::new(if n <= 14 { Band::Two } else { Band::Five }, n, None);
            }
        }
        for word in description.split_whitespace() {
            if let Some(dbm) = word.strip_suffix("dBm") {
                wifi.signal = dbm.parse().ok();
            } else if let Some(fraction) = word.strip_suffix('%') {
                wifi.signal_percent = fraction
                    .parse::<u8>()
                    .ok()
                    .filter(|percent| *percent <= 100);
            }
        }
    }
    wifi.country = words_after(block, "country").and_then(|mut words| country_code(words.next()?));
    wifi
}

fn freebsd_channels(text: &str) -> Vec<Channel> {
    let mut channels: Vec<_> = text
        .split("Channel ")
        .skip(1)
        .filter_map(|entry| {
            let (number, description) = entry.split_once(':')?;
            let frequency = description.split_whitespace().next()?.parse().ok()?;
            Channel::at(frequency, number.trim().parse().ok(), Some(20))
        })
        .collect();
    channels.sort_unstable();
    channels.dedup();
    channels
}

pub fn snapshot(include_channels: bool) -> Snapshot {
    let route = read_command("/sbin/route", &["-n", "get", "default"])
        .map_or_else(Default::default, |text| parse_bsd_route(&text));
    let text = read_command("/sbin/ifconfig", &["-a"]).unwrap_or_default();
    let mut wireless: Vec<_> = wireless_blocks(&text)
        .map(|(name, block)| parse_wifi(name, block))
        .collect();
    let selected = wireless
        .iter()
        .position(|wifi| Some(&wifi.interface) == route.interface.as_ref())
        .or_else(|| wireless.iter().position(|wifi| wifi.connected))
        .or_else(|| (!wireless.is_empty()).then_some(0));
    let Some(mut wifi) = selected.map(|index| wireless.swap_remove(index)) else {
        return Snapshot {
            route,
            note: Some("The system didn’t report a Wi-Fi adapter."),
            ..Snapshot::default()
        };
    };
    // Link channel may be configured while a station is idle.
    if !wifi.connected {
        wifi.channel = None;
        wifi.signal = None;
        wifi.signal_percent = None;
    }
    let channels = if include_channels && cfg!(target_os = "freebsd") {
        read_command("/sbin/ifconfig", &[&wifi.interface, "list", "chan"])
            .map_or_else(Vec::new, |text| freebsd_channels(&text))
    } else {
        Vec::new()
    };
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
    fn parses_station_status_without_network_names() {
        let openbsd = "em0: flags=8843\n\tstatus: active\niwx0: flags=8843\n\tieee80211: nwid Hidden chan 40 bssid 00:11:22:33:44:55 -55dBm\n\tstatus: active\n";
        let (name, text) = wireless_blocks(openbsd).next().unwrap();
        let wifi = parse_wifi(name, text);
        assert_eq!((wifi.interface.as_str(), wifi.signal), ("iwx0", Some(-55)));
        assert_eq!(wifi.channel.unwrap().frequency, 5200);
        let freebsd = "\tssid Hidden channel 5 (5975 MHz 11ax)\n\tregdomain FCC country US\n\tstatus: associated\n";
        let wifi = parse_wifi("wlan0", freebsd);
        assert!(wifi.connected);
        assert_eq!(wifi.channel.unwrap().band, Band::Six);
        assert_eq!(wifi.country.as_deref(), Some("US"));
        let columns =
            "Channel   1 : 2412 MHz 11g  Channel  36 : 5180 MHz 11a\nChannel   1 : 2412 MHz 11g";
        assert_eq!(freebsd_channels(columns).len(), 2);
    }
}
