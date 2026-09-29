//! Hosts the Python runner for the life of the shell: `uv run python -m runner run` from the
//! repo's `runner/` folder, restarted with a backoff if it dies, stopped on pause and on quit.
//!
//! The runner keeps its own single-instance lock, so a runner already started from a terminal
//! is left alone (exit code 3) and retried every minute; a missing sign-in (exit code 4) waits for
//! "Restart runner" from the tray. Output goes to `runner.log` in the app's log folder (the runner
//! never logs mail, tokens or transcripts; CLAUDE.md conventions).

use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Condvar, Mutex, MutexGuard};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

/// Matches `EXIT_ALREADY_RUNNING` / `EXIT_NOT_SIGNED_IN` in runner/runner/__main__.py.
const EXIT_ALREADY_RUNNING: i32 = 3;
const EXIT_NOT_SIGNED_IN: i32 = 4;

const BACKOFF: [Duration; 4] = [
    Duration::from_secs(5),
    Duration::from_secs(15),
    Duration::from_secs(60),
    Duration::from_secs(300),
];
/// A run this long counts as healthy: the next crash starts the backoff over.
const HEALTHY_RUN: Duration = Duration::from_secs(600);
const EXTERNAL_RECHECK: Duration = Duration::from_secs(60);
const NOT_FOUND_RECHECK: Duration = Duration::from_secs(300);
const POLL: Duration = Duration::from_millis(500);
const LOG_ROTATE_BYTES: u64 = 5 * 1024 * 1024;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

#[derive(Clone, Debug, PartialEq)]
pub enum Status {
    Starting,
    Running,
    RetryIn(Duration),
    External,
    NeedsLogin,
    NotFound(String),
    Paused,
    Stopped,
}

impl Status {
    /// Tray label.
    pub fn label(&self) -> String {
        match self {
            Status::Starting => "Runner: starting…".into(),
            Status::Running => "Runner: running".into(),
            Status::RetryIn(d) => format!("Runner: stopped, retrying in {} s", d.as_secs()),
            Status::External => "Runner: running outside the app".into(),
            Status::NeedsLogin => "Runner: sign in first (runner login)".into(),
            Status::NotFound(what) => format!("Runner: {what}"),
            Status::Paused => "Runner: paused".into(),
            Status::Stopped => "Runner: stopped".into(),
        }
    }
}

/// Where the runner lives and how to start it.
#[derive(Clone, Debug)]
pub struct Launch {
    pub uv: PathBuf,
    pub runner_dir: PathBuf,
    pub log: PathBuf,
}

/// Optional `settings.json` in the app's config folder: `{"runner_dir": "...", "uv": "..."}`.
pub fn resolve(config_dir: &Path, log_dir: &Path) -> Result<Launch, String> {
    let settings: serde_json::Value = fs::read_to_string(config_dir.join("settings.json"))
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default();
    let setting = |key: &str| {
        settings
            .get(key)
            .and_then(|v| v.as_str())
            .map(PathBuf::from)
    };

    let runner_dir = [
        setting("runner_dir"),
        std::env::var_os("QUESTBOARD_RUNNER_DIR").map(PathBuf::from),
        // The checkout this shell was built from (single-user: built and run on the same PC).
        Some(Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../runner")),
    ]
    .into_iter()
    .flatten()
    .find(|dir| dir.join("pyproject.toml").is_file())
    .ok_or("runner folder not found (set runner_dir)")?;

    let uv = setting("uv")
        .into_iter()
        .chain(find_on_path("uv"))
        .chain(home_candidates())
        .find(|p| p.is_file())
        .ok_or("uv not found (install uv or set uv)")?;

    Ok(Launch {
        uv,
        runner_dir: runner_dir.canonicalize().unwrap_or(runner_dir),
        log: log_dir.join("runner.log"),
    })
}

fn find_on_path(name: &str) -> Vec<PathBuf> {
    let exe = if cfg!(windows) {
        format!("{name}.exe")
    } else {
        name.to_string()
    };
    std::env::var_os("PATH")
        .map(|path| {
            std::env::split_paths(&path)
                .map(|dir| dir.join(&exe))
                .collect()
        })
        .unwrap_or_default()
}

fn home_candidates() -> Vec<PathBuf> {
    let exe = if cfg!(windows) { "uv.exe" } else { "uv" };
    std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" })
        .map(PathBuf::from)
        .map(|home| {
            vec![
                home.join(".local/bin").join(exe),
                home.join(".cargo/bin").join(exe),
            ]
        })
        .unwrap_or_default()
}

#[derive(Default)]
struct State {
    paused: bool,
    quitting: bool,
    /// Set by `restart`: stop the current child (if any) and start again without waiting.
    restart: bool,
    child: Option<Child>,
}

type OnStatus = Box<dyn Fn(&Status) + Send + Sync>;

struct Shared {
    state: Mutex<State>,
    wake: Condvar,
    on_status: OnStatus,
}

pub struct Supervisor {
    shared: Arc<Shared>,
    thread: Mutex<Option<JoinHandle<()>>>,
}

impl Supervisor {
    /// Starts supervising right away. `launch` is resolved again before every start, so fixing
    /// a missing folder or `uv` needs no restart of the shell.
    pub fn start(
        launch: impl Fn() -> Result<Launch, String> + Send + 'static,
        on_status: impl Fn(&Status) + Send + Sync + 'static,
    ) -> Self {
        let shared = Arc::new(Shared {
            state: Mutex::new(State::default()),
            wake: Condvar::new(),
            on_status: Box::new(on_status),
        });
        let worker = Arc::clone(&shared);
        let thread = thread::Builder::new()
            .name("runner-supervisor".into())
            .spawn(move || supervise(&worker, launch))
            .ok();
        Supervisor {
            shared,
            thread: Mutex::new(thread),
        }
    }

    pub fn is_paused(&self) -> bool {
        self.lock().paused
    }

    /// Pause (stop the runner, no restarts) or resume.
    pub fn set_paused(&self, paused: bool) {
        let mut state = self.lock();
        state.paused = paused;
        if paused {
            kill(&mut state.child);
        }
        drop(state);
        self.shared.wake.notify_all();
    }

    /// Stop the current runner, if any, and start a fresh one now (also clears the backoff).
    pub fn restart(&self) {
        let mut state = self.lock();
        state.paused = false;
        state.restart = true;
        kill(&mut state.child);
        drop(state);
        self.shared.wake.notify_all();
    }

    /// Stop the runner for good and wait for the supervisor to finish.
    pub fn shutdown(&self) {
        let mut state = self.lock();
        state.quitting = true;
        kill(&mut state.child);
        drop(state);
        self.shared.wake.notify_all();
        if let Some(handle) = self.thread.lock().ok().and_then(|mut t| t.take()) {
            let _ = handle.join();
        }
    }

    fn lock(&self) -> MutexGuard<'_, State> {
        self.shared.state.lock().unwrap_or_else(|e| e.into_inner())
    }
}

fn supervise(shared: &Shared, launch: impl Fn() -> Result<Launch, String>) {
    let report = |status: Status| (shared.on_status)(&status);
    let lock = || shared.state.lock().unwrap_or_else(|e| e.into_inner());
    let mut failures = 0usize;

    loop {
        {
            let mut state = lock();
            if state.paused && !state.quitting {
                report(Status::Paused);
                state = shared
                    .wake
                    .wait_while(state, |s| s.paused && !s.quitting)
                    .unwrap_or_else(|e| e.into_inner());
            }
            if state.quitting {
                break;
            }
            state.restart = false;
        }

        let launch = match launch() {
            Ok(launch) => launch,
            Err(why) => {
                report(Status::NotFound(why));
                if sleep(shared, NOT_FOUND_RECHECK) {
                    break;
                }
                continue;
            }
        };

        report(Status::Starting);
        let child = match spawn(&launch) {
            Ok(child) => child,
            Err(why) => {
                report(Status::NotFound(format!("could not start ({why})")));
                if sleep(shared, NOT_FOUND_RECHECK) {
                    break;
                }
                continue;
            }
        };
        let started = Instant::now();
        {
            let mut state = lock();
            if state.quitting || state.paused {
                let mut child = Some(child);
                kill(&mut child);
                continue;
            }
            state.child = Some(child);
        }
        report(Status::Running);

        let code = wait_for_exit(shared);
        let state = lock();
        if state.quitting {
            break;
        }
        if state.paused || state.restart {
            failures = 0;
            continue;
        }
        drop(state);

        let wait = match code {
            Some(EXIT_ALREADY_RUNNING) => {
                report(Status::External);
                EXTERNAL_RECHECK
            }
            Some(EXIT_NOT_SIGNED_IN) => {
                report(Status::NeedsLogin);
                // Nothing to retry until the user signs in and picks "Restart runner".
                let state = lock();
                let state = shared
                    .wake
                    .wait_while(state, |s| !s.quitting && !s.paused && !s.restart)
                    .unwrap_or_else(|e| e.into_inner());
                if state.quitting {
                    break;
                }
                continue;
            }
            _ => {
                if started.elapsed() >= HEALTHY_RUN {
                    failures = 0;
                }
                let wait = BACKOFF[failures.min(BACKOFF.len() - 1)];
                failures += 1;
                report(Status::RetryIn(wait));
                wait
            }
        };
        if sleep(shared, wait) {
            break;
        }
    }
    report(Status::Stopped);
}

/// Waits for the child to exit (or be killed). Returns its exit code if it had one.
fn wait_for_exit(shared: &Shared) -> Option<i32> {
    loop {
        let mut state = shared.state.lock().unwrap_or_else(|e| e.into_inner());
        let Some(child) = state.child.as_mut() else {
            return None; // killed by pause / restart / shutdown
        };
        if let Ok(Some(status)) = child.try_wait() {
            state.child = None;
            return status.code();
        }
        let _ = shared.wake.wait_timeout(state, POLL);
    }
}

/// Sleeps up to `wait`, waking early on pause, restart or quit. Returns true when quitting.
fn sleep(shared: &Shared, wait: Duration) -> bool {
    let state = shared.state.lock().unwrap_or_else(|e| e.into_inner());
    let (state, _) = shared
        .wake
        .wait_timeout_while(state, wait, |s| !s.quitting && !s.paused && !s.restart)
        .unwrap_or_else(|e| e.into_inner());
    state.quitting
}

fn spawn(launch: &Launch) -> std::io::Result<Child> {
    let log = open_log(&launch.log)?;
    let mut cmd = Command::new(&launch.uv);
    cmd.args(["run", "--project"])
        .arg(&launch.runner_dir)
        .args(["python", "-m", "runner", "run"])
        .current_dir(&launch.runner_dir)
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONIOENCODING", "utf-8")
        .stdin(Stdio::null())
        .stdout(log.try_clone()?)
        .stderr(log);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.spawn()
}

fn open_log(path: &Path) -> std::io::Result<File> {
    if let Some(dir) = path.parent() {
        fs::create_dir_all(dir)?;
    }
    if fs::metadata(path)
        .map(|m| m.len() > LOG_ROTATE_BYTES)
        .unwrap_or(false)
    {
        let _ = fs::rename(path, path.with_extension("log.1"));
    }
    let mut file = OpenOptions::new().create(true).append(true).open(path)?;
    let _ = writeln!(file, "=== started by the Questboard desktop shell ===");
    Ok(file)
}

/// Stops the runner and everything it started (`uv` → python → provider CLIs).
fn kill(child: &mut Option<Child>) {
    let Some(mut child) = child.take() else {
        return;
    };
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let _ = Command::new("taskkill")
            .args(["/T", "/F", "/PID", &child.id().to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    }
    let _ = child.kill();
    let _ = child.wait();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn labels_are_short_and_distinct() {
        let all = [
            Status::Starting,
            Status::Running,
            Status::RetryIn(Duration::from_secs(15)),
            Status::External,
            Status::NeedsLogin,
            Status::NotFound("uv not found".into()),
            Status::Paused,
            Status::Stopped,
        ];
        let labels: Vec<String> = all.iter().map(Status::label).collect();
        assert!(
            labels
                .iter()
                .all(|l| l.starts_with("Runner: ") && l.len() < 48)
        );
        let mut unique = labels.clone();
        unique.sort();
        unique.dedup();
        assert_eq!(unique.len(), labels.len());
        assert_eq!(labels[2], "Runner: stopped, retrying in 15 s");
    }

    #[test]
    fn resolve_reads_the_settings_file() {
        let base = std::env::temp_dir().join(format!("qb-runner-test-{}", std::process::id()));
        let runner = base.join("runner");
        fs::create_dir_all(&runner).unwrap();
        fs::write(runner.join("pyproject.toml"), "").unwrap();
        let uv = base.join(if cfg!(windows) { "uv.exe" } else { "uv" });
        fs::write(&uv, "").unwrap();
        let settings = serde_json::json!({ "runner_dir": runner, "uv": uv });
        fs::write(base.join("settings.json"), settings.to_string()).unwrap();

        let launch = resolve(&base, &base.join("logs")).unwrap();
        assert_eq!(launch.uv, uv);
        assert_eq!(launch.runner_dir, runner.canonicalize().unwrap());
        assert_eq!(launch.log, base.join("logs").join("runner.log"));
        fs::remove_dir_all(base).unwrap();
    }

    #[test]
    fn the_build_checkout_is_the_default_runner_folder() {
        let empty = std::env::temp_dir().join(format!("qb-runner-empty-{}", std::process::id()));
        fs::create_dir_all(&empty).unwrap();
        // No settings file: falls back to this repo's runner/ (when uv is installed here).
        if let Ok(launch) = resolve(&empty, &empty) {
            assert!(launch.runner_dir.join("pyproject.toml").is_file());
            assert!(launch.runner_dir.ends_with("runner"));
        }
        fs::remove_dir_all(empty).unwrap();
    }

    /// A fake `runner` package run through the real `uv`: `main` is the body of its __main__.py.
    /// Returns None (test skipped) when uv isn't installed, e.g. on CI.
    fn fake_runner(name: &str, main: &str) -> Option<Launch> {
        let uv = find_on_path("uv")
            .into_iter()
            .chain(home_candidates())
            .find(|p| p.is_file())?;
        let dir = std::env::temp_dir().join(format!("qb-fake-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(dir.join("runner")).unwrap();
        fs::write(
            dir.join("pyproject.toml"),
            "[project]\nname = \"fake-runner\"\nversion = \"0\"\nrequires-python = \">=3.9\"\n\
             dependencies = []\n\n[tool.uv]\npackage = false\n",
        )
        .unwrap();
        fs::write(dir.join("runner").join("__init__.py"), "").unwrap();
        fs::write(dir.join("runner").join("__main__.py"), main).unwrap();
        Some(Launch {
            uv,
            log: dir.join("runner.log"),
            runner_dir: dir,
        })
    }

    fn wait_for(what: &str, secs: u64, mut done: impl FnMut() -> bool) {
        let until = Instant::now() + Duration::from_secs(secs);
        while !done() {
            assert!(Instant::now() < until, "timed out waiting for {what}");
            thread::sleep(Duration::from_millis(100));
        }
    }

    fn statuses(launch: Launch) -> (Supervisor, Arc<Mutex<Vec<Status>>>) {
        let seen = Arc::new(Mutex::new(Vec::new()));
        let log = Arc::clone(&seen);
        let sup = Supervisor::start(
            move || Ok(launch.clone()),
            move |s| log.lock().unwrap().push(s.clone()),
        );
        (sup, seen)
    }

    #[test]
    fn pause_restart_and_quit_stop_the_whole_runner_tree() {
        let Some(launch) = fake_runner(
            "tree",
            "import pathlib, time\nwhile True:\n    pathlib.Path('beat.txt').write_text(str(time.time()))\n    time.sleep(0.1)\n",
        ) else {
            return;
        };
        let beat = launch.runner_dir.join("beat.txt");
        let log = launch.log.clone();
        let dir = launch.runner_dir.clone();
        let read = || fs::read_to_string(&beat).unwrap_or_default();
        let alive = || {
            let before = read();
            thread::sleep(Duration::from_millis(600));
            read() != before
        };
        let (sup, seen) = statuses(launch);

        wait_for("the fake runner to beat", 120, || !read().is_empty());
        assert!(alive());
        assert!(seen.lock().unwrap().contains(&Status::Running));

        sup.set_paused(true); // kills uv and its python child
        assert!(!alive(), "python kept running after pause");
        assert!(seen.lock().unwrap().contains(&Status::Paused));

        sup.set_paused(false);
        wait_for("the runner to come back", 60, alive);

        sup.shutdown();
        assert!(!alive(), "python kept running after quit");
        assert_eq!(seen.lock().unwrap().last(), Some(&Status::Stopped));
        assert!(
            fs::read_to_string(log)
                .unwrap()
                .contains("started by the Questboard desktop shell")
        );
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn exit_codes_mean_external_runner_and_missing_sign_in() {
        for (name, code, expected) in [
            ("external", 3, Status::External),
            ("login", 4, Status::NeedsLogin),
        ] {
            let Some(launch) = fake_runner(name, &format!("import sys\nsys.exit({code})\n")) else {
                return;
            };
            let dir = launch.runner_dir.clone();
            let (sup, seen) = statuses(launch);
            wait_for("the exit to be classified", 120, || {
                seen.lock().unwrap().contains(&expected)
            });
            sup.shutdown();
            let _ = fs::remove_dir_all(dir);
        }
    }

    #[test]
    fn supervises_restarts_and_reports_a_missing_runner() {
        let seen = Arc::new(Mutex::new(Vec::new()));
        let log = Arc::clone(&seen);
        let sup = Supervisor::start(
            || Err("runner folder not found (set runner_dir)".to_string()),
            move |s| log.lock().unwrap().push(s.clone()),
        );
        thread::sleep(Duration::from_millis(200));
        sup.set_paused(true);
        thread::sleep(Duration::from_millis(200));
        assert!(sup.is_paused());
        sup.shutdown();
        let seen = seen.lock().unwrap();
        assert_eq!(
            seen.first(),
            Some(&Status::NotFound(
                "runner folder not found (set runner_dir)".into()
            ))
        );
        assert!(seen.contains(&Status::Paused));
        assert_eq!(seen.last(), Some(&Status::Stopped));
    }
}
