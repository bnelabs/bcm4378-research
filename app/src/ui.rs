use crate::network::{Band, Channel, RadioChange, RouterCheck, Snapshot};
use crate::{network, platform, transfer, travel};
use eframe::egui::{
    self, Align, Button, Color32, ComboBox, Context, Frame, Layout, Margin, RichText, Stroke, Ui,
    Vec2,
};
use std::path::PathBuf;
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;
use std::time::{Duration, Instant};

const BACKGROUND: Color32 = Color32::from_rgb(242, 246, 244);
const SIDEBAR: Color32 = Color32::from_rgb(19, 34, 36);
const SIDEBAR_ACTIVE: Color32 = Color32::from_rgb(37, 62, 60);
const SIDEBAR_TEXT: Color32 = Color32::from_rgb(203, 220, 218);
const SIDEBAR_ACCENT: Color32 = Color32::from_rgb(148, 224, 204);
const PANEL: Color32 = Color32::WHITE;
const BORDER: Color32 = Color32::from_rgb(215, 225, 221);
const PAPER: Color32 = Color32::from_rgb(21, 43, 40);
const MUTED: Color32 = Color32::from_rgb(77, 102, 96);
const MINT: Color32 = Color32::from_rgb(18, 113, 89);
const TINT: Color32 = Color32::from_rgb(228, 241, 235);
const AMBER: Color32 = Color32::from_rgb(136, 72, 28);
const HEADING: &str = "Inter Semibold";

pub fn run(file: Option<PathBuf>, smoke: bool) -> eframe::Result {
    let mut viewport = egui::ViewportBuilder::default()
        .with_title("Know Your Wifi")
        .with_inner_size([1090.0, 740.0])
        .with_min_inner_size([775.0, 565.0]);
    if let Ok(icon) = eframe::icon_data::from_png_bytes(include_bytes!("../Resources/icon.png")) {
        viewport = viewport.with_icon(icon);
    }
    eframe::run_native(
        "Know Your Wifi",
        eframe::NativeOptions {
            viewport,
            renderer: eframe::Renderer::Glow,
            ..Default::default()
        },
        Box::new(move |window| Ok(Box::new(Kyw::new(window.egui_ctx.clone(), file, smoke)))),
    )
}

#[derive(Clone, Copy, PartialEq)]
enum Page {
    Files,
    Connection,
    Channels,
    Controls,
}

enum Event {
    Scan(Box<Snapshot>),
    Router(Result<RouterCheck, &'static str>),
    Radio(Result<(), &'static str>),
    Transfer(u32, transfer::Progress),
    #[cfg(not(target_os = "macos"))]
    Chosen(Option<PathBuf>),
}

struct Kyw {
    input: Receiver<Event>,
    output: Sender<Event>,
    page: Page,
    snapshot: Snapshot,
    refreshing: bool,
    testing: bool,
    router: Option<Result<RouterCheck, &'static str>>,
    pinned_signal: Option<(i16, Option<Channel>)>,
    travel_mode: bool,
    band: Band,
    width: u16,
    first_country: String,
    second_country: String,
    radio_channel: Option<Channel>,
    radio_result: Option<Result<(), &'static str>>,
    confirm: Option<RadioChange>,
    changing: bool,
    file: Option<PathBuf>,
    code: String,
    receiving: bool,
    receipt: Option<transfer::Receiver>,
    transfer_state: Option<transfer::Progress>,
    transfer_id: u32,
    sending: bool,
    copied_at: Option<Instant>,
    icon: Option<egui::TextureHandle>,
    smoke: Option<Instant>,
}

impl Kyw {
    fn new(ctx: Context, file: Option<PathBuf>, smoke: bool) -> Self {
        let (output, input) = mpsc::channel();
        let mut visual = egui::Visuals::light();
        visual.panel_fill = BACKGROUND;
        visual.extreme_bg_color = PANEL;
        visual.override_text_color = Some(PAPER);
        visual.hyperlink_color = MINT;
        visual.selection.bg_fill = TINT;
        visual.selection.stroke = Stroke::new(1.0_f32, MINT);
        for (widget, fill) in [
            (&mut visual.widgets.inactive, BACKGROUND),
            (&mut visual.widgets.hovered, TINT),
            (&mut visual.widgets.active, TINT),
        ] {
            widget.bg_fill = fill;
            widget.weak_bg_fill = fill;
            widget.bg_stroke = Stroke::new(1.0_f32, BORDER);
            widget.fg_stroke = Stroke::new(1.0_f32, PAPER);
            widget.corner_radius = egui::CornerRadius::same(8);
        }
        ctx.set_theme(egui::Theme::Light);
        ctx.set_visuals_of(egui::Theme::Light, visual);
        let mut fonts = egui::FontDefinitions::default();
        fonts.font_data.insert(
            "Inter".into(),
            egui::FontData::from_static(include_bytes!("../Resources/Inter-Regular.ttf")).into(),
        );
        fonts.font_data.insert(
            HEADING.into(),
            egui::FontData::from_static(include_bytes!("../Resources/Inter-SemiBold.ttf")).into(),
        );
        fonts
            .families
            .entry(egui::FontFamily::Proportional)
            .or_default()
            .insert(0, "Inter".into());
        fonts.families.insert(
            egui::FontFamily::Name(HEADING.into()),
            vec![HEADING.into(), "Inter".into()],
        );
        ctx.set_fonts(fonts);
        ctx.style_mut(|style| {
            style.spacing.item_spacing = Vec2::new(10.0, 13.0);
            style.spacing.button_padding = Vec2::new(14.0, 8.0);
            style.spacing.interact_size.y = 34.0;
        });
        let icon = eframe::icon_data::from_png_bytes(include_bytes!("../Resources/icon.png"))
            .ok()
            .map(|image| {
                ctx.load_texture(
                    "KYW icon",
                    egui::ColorImage::from_rgba_unmultiplied(
                        [image.width as usize, image.height as usize],
                        &image.rgba,
                    ),
                    egui::TextureOptions::LINEAR,
                )
            });
        let mut app = Self {
            input,
            output,
            page: Page::Files,
            snapshot: Snapshot::default(),
            refreshing: false,
            testing: false,
            router: None,
            pinned_signal: None,
            travel_mode: false,
            band: Band::Five,
            width: 20,
            first_country: String::new(),
            second_country: String::new(),
            radio_channel: None,
            radio_result: None,
            confirm: None,
            changing: false,
            file,
            code: String::new(),
            receiving: false,
            receipt: None,
            transfer_state: None,
            transfer_id: 0,
            sending: false,
            copied_at: None,
            icon,
            smoke: smoke.then(Instant::now),
        };
        app.refresh(&ctx);
        app
    }

    fn worker(&self, ctx: &Context, run: impl FnOnce() -> Event + Send + 'static) {
        let output = self.output.clone();
        let ctx = ctx.clone();
        thread::spawn(move || {
            let _ = output.send(run());
            ctx.request_repaint();
        });
    }

    fn refresh(&mut self, ctx: &Context) {
        if self.refreshing {
            return;
        }
        self.refreshing = true;
        self.worker(ctx, || Event::Scan(Box::new(platform::snapshot(true))));
    }

    fn collect(&mut self, ctx: &Context) {
        while let Ok(event) = self.input.try_recv() {
            match event {
                Event::Scan(snapshot) => {
                    self.refreshing = false;
                    if self.snapshot.route != snapshot.route {
                        self.router = None;
                    }
                    if self.first_country.is_empty()
                        && let Some(country) = snapshot
                            .wifi
                            .as_ref()
                            .and_then(|wifi| wifi.country.as_ref())
                    {
                        self.first_country = country.clone();
                    }
                    self.snapshot = *snapshot;
                }
                Event::Router(result) => {
                    self.testing = false;
                    self.router = Some(result);
                }
                Event::Radio(result) => {
                    self.changing = false;
                    self.radio_result = Some(result);
                    self.refresh(ctx);
                }
                Event::Transfer(id, status) if id == self.transfer_id => {
                    if matches!(
                        status,
                        transfer::Progress::Sent { .. } | transfer::Progress::Error(_)
                    ) {
                        self.sending = false;
                    }
                    if matches!(status, transfer::Progress::Expired) {
                        self.receipt = None;
                    }
                    self.transfer_state = Some(status);
                }
                Event::Transfer(_, _) => {}
                #[cfg(not(target_os = "macos"))]
                Event::Chosen(path) => {
                    if let Some(path) = path {
                        self.file = Some(path);
                    }
                }
            }
        }
    }

    fn emit(&self, ctx: &Context) -> impl Fn(transfer::Progress) + Send + use<> {
        let output = self.output.clone();
        let id = self.transfer_id;
        let ctx = ctx.clone();
        move |progress| {
            let _ = output.send(Event::Transfer(id, progress));
            ctx.request_repaint();
        }
    }

    fn files(&mut self, ui: &mut Ui) {
        header(
            ui,
            "File handoff",
            "Send a file over your local network, even when the internet is down.",
        );
        let ctx = ui.ctx().clone();
        ui.horizontal(|ui| {
            ui.add_enabled_ui(!self.sending && self.receipt.is_none(), |ui| {
                ui.selectable_value(&mut self.receiving, false, "Send");
                ui.selectable_value(&mut self.receiving, true, "Receive");
            });
        });
        ui.add_space(6.0);
        let pairing = transfer::Pairing::parse(&self.code);
        let paths = if self.receiving {
            self.receipt
                .as_ref()
                .map(|receiver| receiver.pairing.path_count())
        } else {
            pairing.as_ref().map(transfer::Pairing::path_count)
        };
        let available = ui.available_width();
        if available >= 720.0 {
            let detail_width = 250.0;
            let gap = 24.0;
            let form_width = available - detail_width - gap;
            ui.horizontal_top(|ui| {
                ui.spacing_mut().item_spacing.x = gap;
                ui.allocate_ui_with_layout(
                    Vec2::new(form_width, 0.0),
                    Layout::top_down(Align::Min),
                    |ui| {
                        ui.set_max_width(form_width);
                        self.transfer_form(ui, &ctx, pairing);
                    },
                );
                ui.allocate_ui_with_layout(
                    Vec2::new(detail_width, 0.0),
                    Layout::top_down(Align::Min),
                    |ui| {
                        ui.set_max_width(detail_width);
                        local_path(ui, paths);
                    },
                );
            });
        } else {
            self.transfer_form(ui, &ctx, pairing);
            local_path(ui, paths);
        }
    }

    fn transfer_form(&mut self, ui: &mut Ui, ctx: &Context, pairing: Option<transfer::Pairing>) {
        card(ui, |ui| {
            if self.receiving {
                self.receive_form(ui, ctx);
            } else {
                self.send_form(ui, ctx, pairing);
            }
            if let Some(progress) = &self.transfer_state {
                ui.add_space(3.0);
                ui.separator();
                transfer_status(ui, progress);
            }
        });
    }

    fn send_form(&mut self, ui: &mut Ui, ctx: &Context, pairing: Option<transfer::Pairing>) {
        let picked = self
            .file
            .as_ref()
            .and_then(|path| path.file_name()?.to_str())
            .map(str::to_string);
        ui.label(emphasis("File to send", 16.0));
        Frame::new()
            .fill(BACKGROUND)
            .stroke(Stroke::new(1.0_f32, BORDER))
            .corner_radius(10.0)
            .inner_margin(Margin::same(18))
            .show(ui, |ui| {
                ui.set_min_width(ui.available_width());
                ui.set_min_height(84.0);
                if let Some(name) = picked {
                    ui.label(emphasis(name, 16.0));
                    if ui
                        .add_enabled(!self.sending, Button::new("Remove file"))
                        .clicked()
                    {
                        self.file = None;
                    }
                } else {
                    ui.label(emphasis("Drop a file here", 17.0));
                    body(ui, "One file up to 2 GiB");
                    self.file_picker(ui, ctx);
                }
            });
        ui.add_space(4.0);
        ui.label(emphasis("Recipient’s pairing code", 16.0));
        ui.add_enabled(
            !self.sending,
            egui::TextEdit::singleline(&mut self.code)
                .desired_width(ui.available_width())
                .char_limit(320)
                .margin(Margin::symmetric(11, 9))
                .hint_text("Paste code")
                .password(true),
        );
        if !self.code.is_empty() && pairing.is_none() {
            ui.colored_label(AMBER, "Paste the full code copied by the recipient.");
        } else if pairing.is_none() {
            body(ui, "On the other computer, open KYW and choose Receive.");
        }
        ui.add_space(6.0);
        let can_send =
            !self.sending && self.receipt.is_none() && self.file.is_some() && pairing.is_some();
        if ui
            .add_enabled(can_send, action_button("Send file", true))
            .clicked()
            && let (Some(file), Some(pairing)) = (self.file.clone(), pairing)
        {
            self.sending = true;
            self.transfer_id = self.transfer_id.wrapping_add(1);
            self.transfer_state = Some(transfer::Progress::Sending {
                done: 0,
                total: 0,
                resumed: false,
            });
            let emit = self.emit(ctx);
            thread::spawn(move || {
                if let Err(error) = transfer::send_file(&file, pairing, &emit) {
                    emit(transfer::Progress::Error(error));
                }
            });
        }
    }

    fn file_picker(&mut self, ui: &mut Ui, _ctx: &Context) {
        #[cfg(target_os = "macos")]
        if ui
            .add_enabled(!self.sending, action_button("Choose file…", false))
            .clicked()
            && let Some(path) = platform::choose_file()
        {
            self.file = Some(path);
        }
        #[cfg(not(target_os = "macos"))]
        if let Some(chooser) = platform::chooser()
            && ui
                .add_enabled(!self.sending, action_button("Choose file…", false))
                .clicked()
        {
            self.worker(_ctx, move || {
                let path = network::command(
                    chooser,
                    &["--file-selection", "--title=Choose a file for KYW"],
                    Duration::from_secs(120),
                )
                .filter(|result| result.success)
                .map(|result| PathBuf::from(result.text.trim_end_matches('\n')));
                Event::Chosen(path)
            });
        }
    }

    fn receive_form(&mut self, ui: &mut Ui, ctx: &Context) {
        if let Some(receiver) = &self.receipt {
            section(
                ui,
                "Ready to receive",
                "Copy the pairing code and share it with the sender. It lasts ten minutes.",
            );
            let copy_label = if self
                .copied_at
                .is_some_and(|time| time.elapsed() < Duration::from_secs(2))
            {
                "Code copied"
            } else {
                "Copy pairing code"
            };
            let stop = ui
                .horizontal_wrapped(|ui| {
                    if primary(ui, copy_label).clicked() {
                        ctx.copy_text(receiver.pairing.to_string());
                        self.copied_at = Some(Instant::now());
                        ctx.request_repaint_after(Duration::from_secs(2));
                    }
                    ui.button("Stop receiving").clicked()
                })
                .inner;
            if stop {
                self.receipt = None;
                self.copied_at = None;
                self.transfer_id = self.transfer_id.wrapping_add(1);
                self.transfer_state = None;
            }
        } else {
            section(
                ui,
                "Receive a file",
                "Open a receiving window to get a pairing code. Keep the window open until the sender sees that the file arrived.",
            );
            if ui
                .add_enabled(!self.sending, action_button("Start receiving", true))
                .clicked()
            {
                self.transfer_id = self.transfer_id.wrapping_add(1);
                self.transfer_state = None;
                let addresses = transfer::local_addresses();
                let result = transfer::inbox()
                    .ok_or("KYW couldn’t open a folder for received files.")
                    .and_then(|folder| {
                        transfer::start_receiver(&addresses, folder, self.emit(ctx))
                    });
                match result {
                    Ok(receiver) => self.receipt = Some(receiver),
                    Err(error) => self.transfer_state = Some(transfer::Progress::Error(error)),
                }
            }
        }
        ui.add_space(6.0);
        ui.label(emphasis("Where it goes", 15.0));
        body(
            ui,
            "The KYW transfers folder in Downloads, or in your home folder if Downloads is unavailable.",
        );
    }

    fn connection(&mut self, ui: &mut Ui) {
        header(
            ui,
            "Connection check",
            "Check the link to your router and compare the signal in two spots.",
        );
        self.refresh_button(ui);
        let Some(wifi) = &self.snapshot.wifi else {
            card(ui, |ui| {
                body(
                    ui,
                    self.snapshot
                        .note
                        .unwrap_or("KYW is looking for your Wi-Fi adapter."),
                )
            });
            return;
        };
        card(ui, |ui| {
            section(
                ui,
                if wifi.connected {
                    "Connected to Wi-Fi"
                } else {
                    "Wi-Fi is disconnected"
                },
                if self.snapshot.uses_wifi_for_ipv4() {
                    "This computer uses Wi-Fi as its usual IPv4 route."
                } else {
                    "This computer’s usual IPv4 route is elsewhere or unavailable."
                },
            );
            ui.columns(3, |columns| {
                metric(
                    &mut columns[0],
                    "Signal strength",
                    wifi.signal
                        .map(|dbm| format!("{dbm} dBm"))
                        .or(wifi.signal_percent.map(|percent| format!("{percent}%"))),
                );
                metric(
                    &mut columns[1],
                    "Wi-Fi link speed",
                    wifi.rate.map(|rate| format!("{rate:.0} Mb/s")),
                );
                metric(
                    &mut columns[2],
                    "Connected channel",
                    wifi.channel
                        .map(|channel| format!("{} · {}", channel.number, channel.band.label())),
                );
            });
            if let Some(noise) = wifi.noise {
                body(ui, format!("Background radio noise {noise} dBm."));
            }
        });
        card(ui, |ui| {
            section(
                ui,
                "Check your router",
                "Send four short requests to see how quickly it replies.",
            );
            if ui
                .add_enabled(
                    self.snapshot.can_check_router() && !self.testing,
                    Button::new("Run router check"),
                )
                .clicked()
            {
                self.testing = true;
                let route = self.snapshot.route.clone();
                self.worker(ui.ctx(), move || {
                    Event::Router(network::check_router(&route))
                });
            }
            if self.testing {
                ui.spinner();
            } else if let Some(result) = &self.router {
                match result {
                    Ok(check) => {
                        if let Some(median) = check.median() {
                            let longest = check.times_ms.iter().copied().fold(0.0, f32::max);
                            ui.label(format!("{} of 4 replies · Typical {median:.1} ms · Slowest {longest:.1} ms", check.times_ms.len()));
                            body(
                                ui,
                                "Compare this during a slowdown. Delays here can point to the local link, including a busy router.",
                            );
                        } else {
                            body(
                                ui,
                                "No replies. Some routers ignore checks even when Wi-Fi works.",
                            );
                        }
                    }
                    Err(error) => {
                        ui.colored_label(AMBER, *error);
                    }
                }
            } else if !self.snapshot.can_check_router() {
                body(
                    ui,
                    "Connect to a Wi-Fi network with an IPv4 router to run the check.",
                );
            }
        });
        card(ui, |ui| {
            section(
                ui,
                "Compare two spots",
                "Pin the signal, move to a second place, then refresh while using the same Wi-Fi.",
            );
            let signal = self
                .snapshot
                .wifi
                .as_ref()
                .and_then(|wifi| Some((wifi.signal?, wifi.channel)));
            if let Some((reading, channel)) = signal {
                if ui
                    .button(if self.pinned_signal.is_none() {
                        "Pin this reading"
                    } else {
                        "Replace pinned reading"
                    })
                    .clicked()
                {
                    self.pinned_signal = signal;
                }
                if let Some((previous, previous_channel)) = self.pinned_signal {
                    if channel == previous_channel {
                        ui.colored_label(
                            MINT,
                            format!("{:+} dB from the pinned reading", reading - previous),
                        );
                    } else {
                        body(
                            ui,
                            "The channel changed since the pinned reading. Pin a fresh reading to compare the new link.",
                        );
                    }
                }
            } else {
                body(ui, "Signal readings are unavailable on this connection.");
            }
        });
    }

    fn channels(&mut self, ui: &mut Ui) {
        header(
            ui,
            "Channel planner",
            "See the channels listed by your computer or compare stored plans for travel.",
        );
        ui.horizontal(|ui| {
            ui.selectable_value(&mut self.travel_mode, false, "On this computer");
            ui.selectable_value(&mut self.travel_mode, true, "Compare countries");
        });
        card(ui, |ui| {
            if self.travel_mode {
                section(
                    ui,
                    "Broadcom BCM4378 country plans",
                    "Use the stored plans to find channel options in both places.",
                );
                ui.horizontal(|ui| {
                    ui.label("First country");
                    ui.add(
                        egui::TextEdit::singleline(&mut self.first_country)
                            .hint_text("TR")
                            .desired_width(65.0)
                            .char_limit(4),
                    );
                    ui.label("Second country");
                    ui.add(
                        egui::TextEdit::singleline(&mut self.second_country)
                            .hint_text("US")
                            .desired_width(65.0)
                            .char_limit(4),
                    );
                });
            } else {
                section(
                    ui,
                    "Channels listed by this system",
                    "Your current link is highlighted when its primary channel is listed.",
                );
            }
            ui.horizontal(|ui| {
                for band in Band::ALL {
                    ui.selectable_value(&mut self.band, band, band.label());
                }
                ComboBox::from_id_salt("width")
                    .selected_text(format!("{} MHz width", self.width))
                    .show_ui(ui, |ui| {
                        for width in [20, 40, 80, 160] {
                            ui.selectable_value(&mut self.width, width, format!("{width} MHz"));
                        }
                    });
            });
            if self.travel_mode {
                if let Some(comparison) = travel::compare(
                    &self.first_country,
                    &self.second_country,
                    self.band,
                    self.width,
                ) {
                    channel_row(ui, "In both plans", &comparison.common, self.band, None);
                    channel_row(
                        ui,
                        &format!("Only in {}", comparison.first),
                        &comparison.first_only,
                        self.band,
                        None,
                    );
                    channel_row(
                        ui,
                        &format!("Only in {}", comparison.second),
                        &comparison.second_only,
                        self.band,
                        None,
                    );
                } else if !self.second_country.is_empty()
                    && (!travel::knows(&self.first_country) || !travel::knows(&self.second_country))
                {
                    body(
                        ui,
                        "Enter two country codes in the stored plans, for example TR and US.",
                    );
                }
                body(
                    ui,
                    "Wide channels show their center numbers. Check the current rules and your router’s available channels when you arrive.",
                );
            } else {
                let numbers: Vec<_> = self
                    .snapshot
                    .channels
                    .iter()
                    .filter(|channel| {
                        channel.band == self.band && channel.width == Some(self.width)
                    })
                    .map(|channel| channel.number)
                    .collect();
                let active = self
                    .snapshot
                    .wifi
                    .as_ref()
                    .and_then(|wifi| wifi.channel)
                    .filter(|channel| channel.band == self.band)
                    .map(|channel| channel.number);
                channel_row(ui, "Primary channels", &numbers, self.band, active);
                body(
                    ui,
                    "The driver’s list can include channels with extra restrictions. Use your router’s settings when changing its channel.",
                );
            }
        });
    }

    fn controls(&mut self, ui: &mut Ui) {
        header(
            ui,
            "Geek’s Corner",
            "See what runs your Wi-Fi and what settings this system allows.",
        );
        self.refresh_button(ui);
        if let Some(wifi) = &self.snapshot.wifi {
            card(ui, |ui| {
                section(ui, "Your Wi-Fi hardware", "");
                property(
                    ui,
                    "Chip",
                    wifi.chip.as_deref(),
                    "The radio that sends and receives Wi-Fi signals.",
                );
                property(
                    ui,
                    "Firmware",
                    wifi.firmware.as_deref(),
                    "The program that runs on that chip.",
                );
                property(
                    ui,
                    "Radio operating system",
                    wifi.rtos,
                    "It schedules jobs such as radio timing and retries.",
                );
                if let Some(driver) = &wifi.driver {
                    property(
                        ui,
                        "Driver",
                        Some(driver),
                        "It connects the chip to your operating system.",
                    );
                }
                if wifi.rtos.is_some() {
                    ui.hyperlink_to(
                        "Read ThreadX security notices",
                        "https://github.com/eclipse-threadx/threadx/security/advisories",
                    );
                    body(
                        ui,
                        "These notices cover public ThreadX releases. This radio’s vendor build may contain different fixes.",
                    );
                }
            });
        }
        card(ui, |ui| {
            section(ui, "Change Wi-Fi settings", "");
            if let Some(availability) = self.snapshot.radio_control {
                body(ui, availability.reason);
                let powered = self.snapshot.wifi.as_ref().and_then(|wifi| wifi.powered);
                if let Some(powered) = powered {
                    let message = if powered {
                        "Turn Wi-Fi off"
                    } else {
                        "Turn Wi-Fi on"
                    };
                    if ui
                        .add_enabled(availability.enabled && !self.changing, Button::new(message))
                        .clicked()
                    {
                        self.confirm = Some(RadioChange::Power(!powered));
                    }
                }
                ui.add_enabled_ui(
                    availability.enabled && powered == Some(true) && !self.changing,
                    |ui| {
                        ui.horizontal(|ui| {
                            ComboBox::from_id_salt("radio-channel")
                                .selected_text(
                                    self.radio_channel
                                        .map(channel_name)
                                        .unwrap_or_else(|| "Choose a channel".into()),
                                )
                                .show_ui(ui, |ui| {
                                    for &channel in &self.snapshot.channels {
                                        ui.selectable_value(
                                            &mut self.radio_channel,
                                            Some(channel),
                                            channel_name(channel),
                                        );
                                    }
                                });
                            if ui
                                .add_enabled(
                                    self.radio_channel.is_some(),
                                    Button::new("Set idle channel"),
                                )
                                .clicked()
                                && let Some(channel) = self.radio_channel
                            {
                                self.confirm = Some(RadioChange::Channel(channel));
                            }
                        });
                    },
                );
            } else {
                body(
                    ui,
                    format!(
                        "Use {}’s Wi-Fi settings to turn Wi-Fi on or off. Change the connected channel on the router you manage.",
                        platform::name()
                    ),
                );
            }
            if let Some(change) = self.confirm {
                body(
                    ui,
                    match change {
                        RadioChange::Power(false) => {
                            "This stops Wi-Fi and wireless peer links on this Mac."
                        }
                        RadioChange::Power(true) => {
                            "This starts the radio. macOS may reconnect to a saved network."
                        }
                        RadioChange::Channel(_) => {
                            "This tunes the idle radio. A joined network can choose a different channel."
                        }
                    },
                );
                ui.horizontal(|ui| {
                    if primary(ui, "Apply").clicked() {
                        self.confirm = None;
                        self.changing = true;
                        self.worker(ui.ctx(), move || {
                            Event::Radio(platform::change_radio(change))
                        });
                    }
                    if ui.button("Cancel").clicked() {
                        self.confirm = None;
                    }
                });
            }
            if let Some(result) = self.radio_result {
                match result {
                    Ok(()) => {
                        ui.colored_label(MINT, "macOS applied the radio setting.");
                    }
                    Err(error) => {
                        ui.colored_label(AMBER, error);
                    }
                }
            }
        });
    }

    fn refresh_button(&mut self, ui: &mut Ui) {
        ui.horizontal(|ui| {
            if ui
                .add_enabled(!self.refreshing, Button::new("Refresh Wi-Fi"))
                .clicked()
            {
                self.refresh(ui.ctx());
            }
            if self.refreshing {
                ui.spinner();
            }
        });
    }
}

impl eframe::App for Kyw {
    fn update(&mut self, ctx: &Context, _frame: &mut eframe::Frame) {
        self.collect(ctx);
        if let Some(start) = self.smoke {
            if start.elapsed() >= Duration::from_millis(700) {
                ctx.send_viewport_cmd(egui::ViewportCommand::Close);
            } else {
                ctx.request_repaint_after(Duration::from_millis(100));
            }
        }
        if !self.sending
            && let Some(path) = ctx.input(|input| {
                input
                    .raw
                    .dropped_files
                    .iter()
                    .find_map(|file| file.path.clone())
            })
        {
            self.page = Page::Files;
            self.receiving = false;
            self.file = Some(path);
        }
        egui::SidePanel::left("navigation")
            .exact_width(206.0)
            .resizable(false)
            .frame(Frame::new().fill(SIDEBAR).inner_margin(Margin::same(17)))
            .show(ctx, |ui| {
                ui.add_space(16.0);
                ui.horizontal(|ui| {
                    if let Some(icon) = &self.icon {
                        ui.image((icon.id(), Vec2::splat(39.0)));
                    }
                    ui.label(emphasis("Know Your Wifi", 15.5).color(Color32::WHITE));
                });
                ui.add_space(27.0);
                ui.spacing_mut().item_spacing.y = 5.0;
                for (page, title) in [
                    (Page::Files, "File handoff"),
                    (Page::Connection, "Connection check"),
                    (Page::Channels, "Channel planner"),
                    (Page::Controls, "Geek’s Corner"),
                ] {
                    let selected = self.page == page;
                    let text = emphasis(title, 13.0).color(if selected {
                        SIDEBAR_ACCENT
                    } else {
                        SIDEBAR_TEXT
                    });
                    if ui
                        .add_sized(
                            [ui.available_width(), 39.0],
                            Button::new(text)
                                .fill(if selected { SIDEBAR_ACTIVE } else { SIDEBAR })
                                .stroke(Stroke::NONE),
                        )
                        .clicked()
                    {
                        self.page = page;
                    }
                }
                ui.with_layout(Layout::bottom_up(Align::Min), |ui| {
                    ui.add_space(13.0);
                    ui.label(
                        RichText::new(format!(
                            "{}  /  {}",
                            platform::name(),
                            env!("CARGO_PKG_VERSION")
                        ))
                        .size(12.0)
                        .color(SIDEBAR_TEXT),
                    );
                });
            });
        egui::CentralPanel::default()
            .frame(Frame::new().fill(BACKGROUND).inner_margin(Margin::same(35)))
            .show(ctx, |ui| {
                egui::ScrollArea::vertical()
                    .auto_shrink([false, false])
                    .show(ui, |ui| {
                        ui.set_max_width(ui.available_width().min(940.0));
                        match self.page {
                            Page::Files => self.files(ui),
                            Page::Connection => self.connection(ui),
                            Page::Channels => self.channels(ui),
                            Page::Controls => self.controls(ui),
                        }
                    });
            });
    }
}

fn header(ui: &mut Ui, title: &str, subtitle: &str) {
    ui.add_space(3.0);
    ui.label(emphasis(title, 35.0));
    body(ui, subtitle);
    ui.add_space(10.0);
}

fn card(ui: &mut Ui, render: impl FnOnce(&mut Ui)) {
    Frame::new()
        .fill(PANEL)
        .stroke(Stroke::new(1.0_f32, BORDER))
        .corner_radius(14.0)
        .inner_margin(Margin::same(23))
        .show(ui, |ui| {
            ui.set_min_width(ui.available_width());
            render(ui);
        });
}

fn section(ui: &mut Ui, title: &str, detail: &str) {
    ui.label(emphasis(title, 19.0));
    if !detail.is_empty() {
        body(ui, detail);
    }
}

fn emphasis(text: impl Into<String>, size: f32) -> RichText {
    RichText::new(text.into()).font(egui::FontId::new(
        size,
        egui::FontFamily::Name(HEADING.into()),
    ))
}

fn action_button(title: &str, primary: bool) -> Button<'_> {
    Button::new(emphasis(title, 14.0).color(if primary { Color32::WHITE } else { PAPER }))
        .fill(if primary { MINT } else { PANEL })
        .stroke(Stroke::new(1.0_f32, if primary { MINT } else { BORDER }))
        .min_size(Vec2::new(110.0, 39.0))
}

fn primary(ui: &mut Ui, title: &str) -> egui::Response {
    ui.add(action_button(title, true))
}

fn body(ui: &mut Ui, text: impl Into<String>) {
    ui.add(egui::Label::new(RichText::new(text.into()).color(MUTED).size(14.0)).wrap());
}

fn local_path(ui: &mut Ui, paths: Option<usize>) {
    Frame::new().fill(TINT).corner_radius(14.0).inner_margin(Margin::same(19)).show(ui, |ui| {
        ui.set_min_width(ui.available_width());
        ui.label(emphasis("If the link drops", 18.0));
        let available = ui.available_width();
        let (area, _) = ui.allocate_exact_size(Vec2::new(available, 52.0), egui::Sense::hover());
        let start = egui::pos2(area.left() + 25.0, area.center().y);
        let end = egui::pos2(area.right() - 25.0, area.center().y);
        let painter = ui.painter_at(area);
        let line = Stroke::new(1.5_f32, if paths.is_some() { MINT } else { MUTED });
        if paths.unwrap_or_default() > 1 {
            for lift in [-9.0, 9.0] {
                painter.add(egui::Shape::line(
                    vec![start, egui::pos2(start.x + 28.0, start.y + lift),
                         egui::pos2(end.x - 28.0, end.y + lift), end], line
                ));
            }
        } else {
            painter.line_segment([start, end], line);
        }
        for point in [start, end] {
            let screen = egui::Rect::from_center_size(point, Vec2::new(34.0, 24.0));
            painter.rect(screen, 5.0, TINT, line, egui::StrokeKind::Inside);
            painter.line_segment([point + Vec2::new(-9.0, 16.0), point + Vec2::new(9.0, 16.0)], line);
        }
        if let Some(count) = paths {
            let text = if count == 1 { "1 address to try".into() } else { format!("{count} addresses to try") };
            ui.label(emphasis(text, 13.0).color(MINT));
        }
        body(ui, "KYW keeps what arrived and picks up from there when it reconnects.");
        body(ui, "A second reachable address can keep the transfer going if the first connection fails.");
    });
}

fn transfer_status(ui: &mut Ui, status: &transfer::Progress) {
    match status {
        transfer::Progress::Sending {
            done,
            total,
            resumed,
        } => progress_bar(
            ui,
            *done,
            *total,
            if *resumed {
                "Sending from where it stopped"
            } else {
                "Sending"
            },
        ),
        transfer::Progress::Receiving { done, total } => {
            progress_bar(ui, *done, *total, "Receiving")
        }
        transfer::Progress::Sent {
            name,
            bytes,
            resumed,
            changed_address,
        } => {
            let title = match (*resumed, *changed_address) {
                (true, true) => "File delivered over another connection",
                (true, false) => "Sent after reconnecting",
                _ => "File delivered",
            };
            ui.label(emphasis(title, 16.0).color(MINT));
            body(ui, format!("{name} · {}", byte_count(*bytes)));
        }
        transfer::Progress::Saved { name, bytes } => {
            ui.label(emphasis("File saved", 16.0).color(MINT));
            body(ui, format!("{name} · {}", byte_count(*bytes)));
        }
        transfer::Progress::Error(error) => {
            ui.colored_label(AMBER, *error);
        }
        transfer::Progress::Expired => {
            ui.colored_label(
                AMBER,
                "The pairing code expired. Start a new receiving window.",
            );
        }
    }
}

fn metric(ui: &mut Ui, title: &str, value: Option<String>) {
    body(ui, title);
    ui.label(
        RichText::new(value.unwrap_or_else(|| "Unavailable".into()))
            .size(20.0)
            .color(MINT),
    );
}

fn property(ui: &mut Ui, name: &str, value: Option<&str>, detail: &str) {
    ui.label(emphasis(
        format!("{name}   {}", value.unwrap_or("Unavailable")),
        15.0,
    ));
    body(ui, detail);
}

fn channel_name(channel: Channel) -> String {
    format!(
        "Channel {} · {} · {} MHz",
        channel.number,
        channel.band.label(),
        channel.width.unwrap_or(20)
    )
}

fn channel_row(ui: &mut Ui, title: &str, channels: &[u16], band: Band, active: Option<u16>) {
    ui.label(RichText::new(title).size(14.0).strong());
    if channels.is_empty() {
        body(ui, "None listed at this width.");
    } else {
        ui.horizontal_wrapped(|ui| {
            for &channel in channels {
                let high = active == Some(channel);
                Frame::new()
                    .fill(if high { TINT } else { BACKGROUND })
                    .corner_radius(6.0)
                    .inner_margin(Margin::symmetric(8, 4))
                    .show(ui, |ui| {
                        ui.label(
                            RichText::new(format!("{channel}"))
                                .monospace()
                                .color(if high { MINT } else { PAPER }),
                        )
                        .on_hover_text(format!(
                            "{} MHz{}",
                            band.mhz(channel),
                            if high { " · Current primary" } else { "" }
                        ));
                    });
            }
        });
    }
}

fn byte_count(bytes: u64) -> String {
    if bytes < 1024 {
        format!("{bytes} bytes")
    } else if bytes < 1024 * 1024 {
        format!("{:.1} KiB", bytes as f64 / 1024.0)
    } else {
        format!("{:.1} MiB", bytes as f64 / (1024.0 * 1024.0))
    }
}

fn progress_bar(ui: &mut Ui, done: u64, total: u64, label: &str) {
    if total == 0 {
        ui.horizontal(|ui| {
            ui.spinner();
            body(ui, "Preparing the file…");
        });
    } else {
        ui.label(emphasis(
            format!("{label} · {} of {}", byte_count(done), byte_count(total)),
            14.0,
        ));
        ui.add(
            egui::ProgressBar::new((done as f64 / total as f64) as f32)
                .fill(MINT)
                .desired_width(ui.available_width())
                .desired_height(8.0),
        );
    }
}
