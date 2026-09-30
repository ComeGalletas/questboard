//! The companion overlay: a frameless, transparent, always-on-top window with the persona sprite
//! (web route `/companion`). The window ignores the mouse except over the boxes the page
//! reports (sprite, bubble, menu), hides while a fullscreen app runs, and remembers where it was
//! dragged and whether the tray's "Show companion" is on.

use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::Duration;

use serde::Deserialize;
use tauri::menu::CheckMenuItem;
use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, State, WebviewWindow, Wry};

pub const LABEL: &str = "companion";
const HIDDEN_MARKER: &str = "companion-hidden";
const POSITION_FILE: &str = "companion-position";
const TICK: Duration = Duration::from_millis(50);
/// Fullscreen is checked every this many ticks (~2 s).
const FULLSCREEN_EVERY: u32 = 40;
/// Gap between the window and the screen corner, in logical px.
const MARGIN: f64 = 16.0;

/// A box that takes the pointer, in CSS px relative to the window's content.
#[derive(Clone, Copy, Debug, Deserialize, PartialEq)]
pub struct HitArea {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

impl HitArea {
    /// Whether a point in physical px relative to the content's origin is inside, at `scale`.
    fn contains(&self, px: f64, py: f64, scale: f64) -> bool {
        px >= self.x * scale
            && px < (self.x + self.width) * scale
            && py >= self.y * scale
            && py < (self.y + self.height) * scale
    }
}

pub struct Companion {
    areas: Mutex<Vec<HitArea>>,
    /// The tray's "Show companion".
    wanted: AtomicBool,
    menu_item: Mutex<Option<CheckMenuItem<Wry>>>,
    config_dir: Option<PathBuf>,
}

impl Companion {
    pub fn new(config_dir: Option<PathBuf>) -> Self {
        let hidden = config_dir
            .as_ref()
            .is_some_and(|d| d.join(HIDDEN_MARKER).exists());
        Companion {
            areas: Mutex::new(Vec::new()),
            wanted: AtomicBool::new(!hidden),
            menu_item: Mutex::new(None),
            config_dir,
        }
    }

    pub fn wanted(&self) -> bool {
        self.wanted.load(Ordering::Relaxed)
    }

    pub fn set_menu_item(&self, item: CheckMenuItem<Wry>) {
        if let Ok(mut slot) = self.menu_item.lock() {
            *slot = Some(item);
        }
    }

    /// Tray toggle / "Hide companion": remembered on this PC.
    pub fn set_wanted(&self, wanted: bool) {
        self.wanted.store(wanted, Ordering::Relaxed);
        if let Some(dir) = &self.config_dir {
            let marker = dir.join(HIDDEN_MARKER);
            let _ = if wanted {
                fs::remove_file(marker)
            } else {
                fs::create_dir_all(dir).and_then(|()| fs::write(marker, b"1"))
            };
        }
        if let Ok(slot) = self.menu_item.lock()
            && let Some(item) = slot.as_ref()
        {
            let _ = item.set_checked(wanted);
        }
    }

    /// Remember where the user dragged it.
    pub fn save_position(&self, pos: PhysicalPosition<i32>) {
        if let Some(dir) = &self.config_dir {
            let _ = fs::create_dir_all(dir);
            let _ = fs::write(dir.join(POSITION_FILE), format!("{} {}", pos.x, pos.y));
        }
    }

    fn saved_position(&self) -> Option<PhysicalPosition<i32>> {
        let text = fs::read_to_string(self.config_dir.as_ref()?.join(POSITION_FILE)).ok()?;
        parse_position(&text)
    }
}

fn parse_position(text: &str) -> Option<PhysicalPosition<i32>> {
    let mut parts = text.split_whitespace().map(str::parse::<i32>);
    match (parts.next(), parts.next(), parts.next()) {
        (Some(Ok(x)), Some(Ok(y)), None) => Some(PhysicalPosition::new(x, y)),
        _ => None,
    }
}

/// The saved spot if it's still on a monitor, else the primary monitor's bottom-right corner.
pub fn place(window: &WebviewWindow, companion: &Companion) {
    let Ok(size) = window.outer_size() else {
        return;
    };
    let monitors = window.available_monitors().unwrap_or_default();
    let on_screen = |p: &PhysicalPosition<i32>| {
        monitors.iter().any(|m| {
            let (a, s) = (m.work_area().position, m.work_area().size);
            p.x >= a.x && p.y >= a.y && p.x < a.x + s.width as i32 && p.y < a.y + s.height as i32
        })
    };
    if let Some(saved) = companion.saved_position().filter(on_screen) {
        let _ = window.set_position(saved);
        return;
    }
    if let Ok(Some(monitor)) = window.primary_monitor() {
        let area = monitor.work_area();
        let margin = (MARGIN * monitor.scale_factor()) as i32;
        let x = area.position.x + area.size.width as i32 - size.width as i32 - margin;
        let y = area.position.y + area.size.height as i32 - size.height as i32 - margin;
        let _ = window.set_position(PhysicalPosition::new(x, y));
    }
}

/// Shows or hides the window with the preference and fullscreen apps, and turns mouse
/// pass-through off only while the pointer is over a hit area. Runs for the app's lifetime.
pub fn watch(app: AppHandle) {
    thread::spawn(move || {
        let mut shown = false;
        let mut interactive = true;
        let mut fullscreen = false;
        let mut tick = 0u32;
        loop {
            thread::sleep(TICK);
            let Some(window) = app.get_webview_window(LABEL) else {
                continue;
            };
            let companion = app.state::<Companion>();
            if tick.is_multiple_of(FULLSCREEN_EVERY) {
                fullscreen = fullscreen_app_running();
            }
            tick = tick.wrapping_add(1);

            let show = companion.wanted() && !fullscreen;
            if show != shown {
                let _ = if show { window.show() } else { window.hide() };
                shown = show;
            }
            if !shown {
                continue;
            }
            let over = match (window.cursor_position(), window.inner_position()) {
                (Ok(cursor), Ok(origin)) => {
                    let scale = window.scale_factor().unwrap_or(1.0);
                    let (px, py) = (
                        cursor.x - f64::from(origin.x),
                        cursor.y - f64::from(origin.y),
                    );
                    companion
                        .areas
                        .lock()
                        .map(|areas| areas.iter().any(|a| a.contains(px, py, scale)))
                        .unwrap_or(false)
                }
                _ => false,
            };
            if over != interactive {
                let _ = window.set_ignore_cursor_events(!over);
                interactive = over;
            }
        }
    });
}

/// A fullscreen game, video or presentation owns the screen (Windows' own "busy" states).
#[cfg(windows)]
fn fullscreen_app_running() -> bool {
    use windows::Win32::UI::Shell::{
        QUNS_APP, QUNS_BUSY, QUNS_PRESENTATION_MODE, QUNS_RUNNING_D3D_FULL_SCREEN,
        SHQueryUserNotificationState,
    };
    matches!(
        unsafe { SHQueryUserNotificationState() },
        Ok(state) if [QUNS_BUSY, QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE, QUNS_APP]
            .contains(&state)
    )
}

#[cfg(not(windows))]
fn fullscreen_app_running() -> bool {
    false
}

#[tauri::command]
pub fn companion_hit_areas(areas: Vec<HitArea>, companion: State<'_, Companion>) {
    if let Ok(mut slot) = companion.areas.lock() {
        *slot = areas.into_iter().take(16).collect();
    }
}

/// Dashboard -> companion: say this (a PC notification's reaction).
#[tauri::command]
pub fn companion_say(app: AppHandle, cue: serde_json::Value) -> Result<(), String> {
    app.emit_to(LABEL, "companion-say", cue)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn companion_drag(window: WebviewWindow) -> Result<(), String> {
    window.start_dragging().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn open_dashboard(app: AppHandle) {
    crate::show_dashboard(&app);
}

#[tauri::command]
pub fn hide_companion(companion: State<'_, Companion>) {
    companion.set_wanted(false);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hit_areas_scale_with_the_display() {
        let sprite = HitArea {
            x: 160.0,
            y: 200.0,
            width: 96.0,
            height: 96.0,
        };
        assert!(sprite.contains(170.0, 210.0, 1.0));
        assert!(!sprite.contains(150.0, 210.0, 1.0));
        // At 150 % the same CSS box covers physical 240..384 x 300..444.
        assert!(sprite.contains(250.0, 310.0, 1.5));
        assert!(!sprite.contains(170.0, 210.0, 1.5));
        assert!(
            !sprite.contains(384.0, 310.0, 1.5),
            "right edge is exclusive"
        );
    }

    #[test]
    fn saved_positions_parse_strictly() {
        assert_eq!(
            parse_position("1520 800"),
            Some(PhysicalPosition::new(1520, 800))
        );
        assert_eq!(
            parse_position("-1900 40\n"),
            Some(PhysicalPosition::new(-1900, 40))
        );
        assert_eq!(parse_position("12"), None);
        assert_eq!(parse_position("1 2 3"), None);
        assert_eq!(parse_position("x y"), None);
    }

    #[test]
    fn the_preference_is_remembered() {
        let dir = std::env::temp_dir().join(format!("qb-companion-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        let companion = Companion::new(Some(dir.clone()));
        assert!(companion.wanted(), "shown by default");
        companion.set_wanted(false);
        assert!(
            !Companion::new(Some(dir.clone())).wanted(),
            "hidden after a restart"
        );
        companion.set_wanted(true);
        assert!(Companion::new(Some(dir.clone())).wanted());
        companion.save_position(PhysicalPosition::new(10, 20));
        assert_eq!(
            companion.saved_position(),
            Some(PhysicalPosition::new(10, 20))
        );
        let _ = fs::remove_dir_all(dir);
    }
}
