//! Questboard desktop shell (Tauri glue only; the UI is the web app's static build).
//!
//! - `dashboard` window: hides on close, so the app keeps living in the tray.
//! - Tray: open the dashboard, runner status + pause / restart / log, start at login, quit.
//! - Runner: hosted by `runner::Supervisor` (`uv run python -m runner run` from this repo).
//! - Start at login: on by default (CLAUDE.md "Starts at login"), launched with `--minimized`
//!   so it waits in the tray. The user can turn it off from the tray.
//! - `questboard://` deep links: a single instance receives them (cold start or forwarded from a
//!   second launch), keeps the latest one and tells the web app, which takes it with
//!   `take_deep_link` and routes it through `lib/deeplink.ts`.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod runner;

use std::fs;
use std::process::Command;
use std::sync::Mutex;

use tauri::menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State, WindowEvent, Wry};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};
use tauri_plugin_deep_link::DeepLinkExt;

const DASHBOARD: &str = "dashboard";
const MINIMIZED: &str = "--minimized";
const SCHEME: &str = "questboard://";
/// Written once start at login has been set up, so turning it off in the tray sticks.
const AUTOSTART_MARKER: &str = "autostart-initialized";

#[derive(Default)]
struct PendingLink(Mutex<Option<String>>);

/// The web app takes the latest deep link (at most once).
#[tauri::command]
fn take_deep_link(pending: State<'_, PendingLink>) -> Option<String> {
    pending.0.lock().ok()?.take()
}

fn show_dashboard(app: &AppHandle) {
    if let Some(window) = app.get_webview_window(DASHBOARD) {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn open_links(app: &AppHandle, urls: impl IntoIterator<Item = String>) {
    let Some(url) = urls.into_iter().filter(|u| u.starts_with(SCHEME)).last() else {
        return;
    };
    if let Ok(mut slot) = app.state::<PendingLink>().0.lock() {
        *slot = Some(url);
    }
    show_dashboard(app);
    let _ = app.emit_to(DASHBOARD, "deep-link", ());
}

/// Turn start at login on the first time the app runs; after that the tray toggle owns it.
/// Release builds only: a dev build would register the `target/` executable at login.
fn init_autostart(app: &AppHandle) {
    if cfg!(debug_assertions) {
        return;
    }
    let Ok(dir) = app.path().app_config_dir() else {
        return;
    };
    let marker = dir.join(AUTOSTART_MARKER);
    if marker.exists() {
        // Keep the login entry on the executable that is running now (e.g. the installed app
        // after a build was run straight from target/release): enabling rewrites its path.
        let launcher = app.autolaunch();
        if launcher.is_enabled().unwrap_or(false) {
            let _ = launcher.enable();
        }
        return;
    }
    if app.autolaunch().enable().is_ok() && fs::create_dir_all(&dir).is_ok() {
        let _ = fs::write(marker, b"1");
    }
}

/// Tray items the runner supervisor updates.
struct RunnerItems {
    status: MenuItem<Wry>,
    pause: MenuItem<Wry>,
}

fn build_tray(app: &AppHandle) -> tauri::Result<RunnerItems> {
    let open = MenuItem::with_id(app, "open", "Open Questboard", true, None::<&str>)?;
    let status = MenuItem::with_id(
        app,
        "runner-status",
        "Runner: starting…",
        false,
        None::<&str>,
    )?;
    let pause = MenuItem::with_id(app, "runner-pause", "Pause runner", true, None::<&str>)?;
    let restart = MenuItem::with_id(app, "runner-restart", "Restart runner", true, None::<&str>)?;
    let log = MenuItem::with_id(app, "runner-log", "Open runner log", true, None::<&str>)?;
    let autostart_on = app.autolaunch().is_enabled().unwrap_or(false);
    let autostart = CheckMenuItem::with_id(
        app,
        "autostart",
        "Start at login",
        true,
        autostart_on,
        None::<&str>,
    )?;
    let quit = MenuItem::with_id(app, "quit", "Quit Questboard", true, None::<&str>)?;
    let menu = Menu::with_items(
        app,
        &[
            &open,
            &PredefinedMenuItem::separator(app)?,
            &status,
            &pause,
            &restart,
            &log,
            &PredefinedMenuItem::separator(app)?,
            &autostart,
            &quit,
        ],
    )?;

    let mut tray = TrayIconBuilder::with_id("main")
        .tooltip("Questboard")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(move |app, event| match event.id().as_ref() {
            "open" => show_dashboard(app),
            "runner-pause" => {
                let sup = app.state::<runner::Supervisor>();
                sup.set_paused(!sup.is_paused());
            }
            "runner-restart" => app.state::<runner::Supervisor>().restart(),
            "runner-log" => open_runner_log(app),
            "autostart" => {
                let launcher = app.autolaunch();
                let on = launcher.is_enabled().unwrap_or(false);
                let _ = if on {
                    launcher.disable()
                } else {
                    launcher.enable()
                };
                let _ = autostart.set_checked(launcher.is_enabled().unwrap_or(on));
            }
            "quit" => {
                app.state::<runner::Supervisor>().shutdown();
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_dashboard(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        tray = tray.icon(icon.clone());
    }
    tray.build(app)?;
    Ok(RunnerItems { status, pause })
}

fn open_runner_log(app: &AppHandle) {
    if let Ok(dir) = app.path().app_log_dir() {
        let log = dir.join("runner.log");
        if log.is_file() {
            let _ = Command::new("explorer").arg(log).spawn();
        }
    }
}

/// Starts hosting the runner and keeps the tray's runner items in step with it.
fn start_runner(app: &AppHandle, items: RunnerItems) -> tauri::Result<()> {
    let config_dir = app.path().app_config_dir()?;
    let log_dir = app.path().app_log_dir()?;
    let supervisor = runner::Supervisor::start(
        move || runner::resolve(&config_dir, &log_dir),
        move |status| {
            let _ = items.status.set_text(status.label());
            let paused = *status == runner::Status::Paused;
            let _ = items.pause.set_text(if paused {
                "Resume runner"
            } else {
                "Pause runner"
            });
        },
    );
    app.manage(supervisor);
    Ok(())
}

fn main() {
    tauri::Builder::default()
        // First: a second launch (or a deep link opened while running) focuses this instance;
        // with the deep-link feature, forwarded URLs reach `on_open_url` below.
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            show_dashboard(app);
        }))
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec![MINIMIZED]),
        ))
        .manage(PendingLink::default())
        .invoke_handler(tauri::generate_handler![take_deep_link])
        .setup(|app| {
            let handle = app.handle().clone();

            // Installers register the scheme; this also covers dev builds and moved installs.
            #[cfg(any(windows, target_os = "linux"))]
            app.deep_link().register_all()?;
            if let Some(urls) = app.deep_link().get_current()? {
                open_links(&handle, urls.into_iter().map(String::from));
            }
            let links = handle.clone();
            app.deep_link().on_open_url(move |event| {
                open_links(&links, event.urls().into_iter().map(String::from));
            });

            init_autostart(&handle);
            let items = build_tray(&handle)?;
            start_runner(&handle, items)?;

            if !std::env::args().any(|arg| arg == MINIMIZED) {
                show_dashboard(&handle);
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event
                && window.label() == DASHBOARD
            {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building the Questboard desktop shell")
        .run(|app, event| {
            // However the app ends (tray quit, OS shutdown), take the runner down with it.
            if let RunEvent::Exit = event
                && let Some(sup) = app.try_state::<runner::Supervisor>()
            {
                sup.shutdown();
            }
        });
}
