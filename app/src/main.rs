mod network;
mod platform;
mod transfer;
mod travel;
mod ui;

use std::path::PathBuf;
use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    match args.first().and_then(|arg| arg.to_str()) {
        Some("--check") => {
            let snapshot = platform::snapshot(true);
            println!("Know Your Wifi {}", env!("CARGO_PKG_VERSION"));
            println!("System: {}", platform::name());
            if let Some(wifi) = &snapshot.wifi {
                println!(
                    "Wi-Fi: {}",
                    if wifi.connected {
                        "connected"
                    } else {
                        "disconnected"
                    }
                );
                if let Some(chip) = &wifi.chip {
                    println!("Chip: {chip}");
                }
                if let Some(firmware) = &wifi.firmware {
                    println!("Firmware: {firmware}");
                }
                if let Some(rtos) = wifi.rtos {
                    println!("Radio operating system: {rtos}");
                }
                if let Some(country) = &wifi.country {
                    println!("Country: {country}");
                }
                if let Some(channel) = wifi.channel {
                    println!("Channel: {} on {}", channel.number, channel.band.label());
                }
                if let Some(signal) = wifi.signal {
                    println!("Signal: {signal} dBm");
                }
                println!("Listed channels: {}", snapshot.channels.len());
            } else {
                println!("{}", snapshot.note.unwrap_or("No Wi-Fi adapter found."));
            }
            println!(
                "Default IPv4 route uses Wi-Fi: {}",
                if snapshot.uses_wifi_for_ipv4() {
                    "yes"
                } else {
                    "no"
                }
            );
            ExitCode::SUCCESS
        }
        Some("--self-test") => match transfer::self_test() {
            Ok(()) => {
                println!(
                    "Encrypted local file transfer resumed on the alternate listener. The wrong code was rejected and the file matched."
                );
                ExitCode::SUCCESS
            }
            Err(error) => {
                eprintln!("{error}");
                ExitCode::FAILURE
            }
        },
        Some("--compare") if args.len() == 3 => {
            let first = args[1].to_str().unwrap_or_default();
            let second = args[2].to_str().unwrap_or_default();
            if let Some(result) = travel::compare(first, second, network::Band::Five, 20) {
                println!("BCM4378 stored 5 GHz plan, 20 MHz channel width");
                println!(
                    "{} and {}: {:?}",
                    result.first, result.second, result.common
                );
                println!("Only {}: {:?}", result.first, result.first_only);
                println!("Only {}: {:?}", result.second, result.second_only);
                ExitCode::SUCCESS
            } else {
                eprintln!("Enter two country codes in the bundled plan, such as TR US.");
                ExitCode::FAILURE
            }
        }
        Some("--help") => {
            println!(
                "Know Your Wifi\n  kyw                  Open the desktop app\n  kyw FILE             Choose a file to send\n  kyw --check          Read your current Wi-Fi status\n  kyw --compare TR US  Compare stored channel plans\n  kyw --self-test      Test offline file transfer on this computer"
            );
            ExitCode::SUCCESS
        }
        _ => {
            let smoke = args.first().is_some_and(|arg| arg == "--ui-smoke");
            let file = if smoke {
                None
            } else {
                args.first()
                    .map(PathBuf::from)
                    .filter(|path| path.is_file())
            };
            match ui::run(file, smoke) {
                Ok(()) => ExitCode::SUCCESS,
                Err(_) => {
                    eprintln!(
                        "KYW couldn’t open a desktop window. Start it in a graphical session with OpenGL support."
                    );
                    ExitCode::FAILURE
                }
            }
        }
    }
}
