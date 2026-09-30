"""Runner entry point.

  python -m runner login                     one-time: Supabase URL/key + sign in (keychain)
  python -m runner run [--dry-run]           trigger loop (start, 5-min tick, network up)
  python -m runner tick [--dry-run]          one evaluation, then exit
  python -m runner trigger JOB [--dry-run] [--force]
                                             manual run of one job; --force re-runs its latest
                                             occurrence even if it succeeded (new attempt, max 3)
  python -m runner vapid                     print a new VAPID key pair for Web Push
  python -m runner notify-test [KIND]        send a test Web Push (default day_ready) to every
                                             subscribed device now: no quiet hours, dedup or
                                             max age; nothing written to notifications
  python -m runner packs                     check the persona packs (errors and warnings)
  python -m runner vault                     open (or create) the local vault; prints counts only

--dry-run uses an in-memory DB with the default config. Output lists job decisions only,
never data.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sys

from questboard_schema.common_schema import JobName, NotificationKind, ProviderName
from questboard_schema.config_schema import Config
from questboard_schema.llm_run_schema import Trigger

from runner.engine.packs import inspect_packs
from runner.jobs import HANDLERS
from runner.notify.push import generate_vapid_keys, sender_from_env
from runner.notify.selftest import NotifyTestError, send_test
from runner.notify.step import run_notifications
from runner.paths import data_dir
from runner.providers import ClaudeCliProvider, Provider
from runner.providers.claude_api import ClaudeApiProvider
from runner.providers.ollama import OllamaProvider
from runner.repo import MemoryRepo, Repo, RepoUnavailable
from runner.scheduler.core import Scheduler
from runner.scheduler.lock import AlreadyRunning, InstanceLock
from runner.scheduler.loop import Loop
from runner.settings import Settings, SettingsMissing
from runner.supabase_repo import KeyringTokenStore, SupabaseRepo

# Exit codes the desktop shell tells apart (apps/desktop/src-tauri/src/runner.rs).
EXIT_ALREADY_RUNNING = 3  # another runner holds the lock: leave it be
EXIT_NOT_SIGNED_IN = 4  # no Supabase settings: `python -m runner login` first

# Libraries that log every request at INFO: the live-request poll alone would add three lines
# every 5 s and bury the job decisions. Their warnings and errors still come through.
QUIET_LOGGERS = ("httpx", "httpcore")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


DEFAULT_CONFIG = {
    "timezone": "America/Bogota",
    "goals": [],
    "capacity": {"weekday_hours": 3, "weekend_hours": 5, "focus_factor": 0.7},
    "quiet_hours": {"start": "22:00", "end": "07:00"},
    "xp_weights": {},
    "llm": {"providers": ["claude-cli", "ollama", "claude-api"]},
    "persona_order": ["coach", "teacher", "mom", "quartermaster"],
    "integrations": {"gmail": False, "gcal": False},
    "features": {"three_d": False, "mobile_rehydration": False},
    "notifications": {"persona_speech_per_day": 2, "persona_speech_on_mobile": False},
}


def providers_for(config: Config) -> dict[ProviderName, Provider]:
    """All providers, with per-provider models from config.llm.models when set."""
    models = {name: m.root for name, m in (config.llm.models or {}).items()}
    cli = ClaudeCliProvider(model=models.get(ProviderName.claude_cli))
    ollama = OllamaProvider(**_model(models, ProviderName.ollama))
    api = ClaudeApiProvider(**_model(models, ProviderName.claude_api))
    return {p.name: p for p in (cli, ollama, api)}


def _model(models: dict[ProviderName, str], name: ProviderName) -> dict[str, str]:
    return {"model": models[name]} if name in models else {}


def build(dry_run: bool) -> Scheduler:
    repo: Repo
    if dry_run:
        repo = MemoryRepo(Config.model_validate(DEFAULT_CONFIG))
    else:
        settings = Settings.load()
        repo = SupabaseRepo(settings.supabase_url, settings.supabase_anon_key, KeyringTokenStore())
    try:
        config = repo.get_config()
    except RepoUnavailable:
        config = Config.model_validate(DEFAULT_CONFIG)  # offline at boot: defaults until reconnect
    send = sender_from_env()
    return Scheduler(
        repo=repo,
        handlers=HANDLERS,
        providers=providers_for(config),
        after_jobs=lambda r, cfg, now: run_notifications(r, cfg, now, send),
        push=send,
    )


def login() -> int:
    try:
        settings = Settings.load()
    except SettingsMissing:
        settings = Settings(input("Supabase URL: ").strip(), input("Supabase anon key: ").strip())
        settings.save()
    repo = SupabaseRepo(settings.supabase_url, settings.supabase_anon_key, KeyringTokenStore())
    repo.sign_in(input("Email: ").strip(), getpass.getpass("Password: "))
    print("Signed in; session stored in the OS keychain.")
    return 0


OUTCOMES = {"sent": "sent", "removed": "expired endpoint removed", "failed": "failed"}


def notify_test(kind: str, repo: Repo | None = None) -> int:
    """Sends one test push to every device and prints per-device outcomes (no endpoints/keys).
    Exit 1 when nothing was delivered."""
    send = sender_from_env()
    try:
        if repo is None:
            settings = Settings.load()
            repo = SupabaseRepo(
                settings.supabase_url, settings.supabase_anon_key, KeyringTokenStore()
            )
        result = send_test(repo, repo.get_config(), NotificationKind(kind), send)
    except (NotifyTestError, RepoUnavailable, SettingsMissing) as exc:
        print(f"notify-test: {exc}", file=sys.stderr)
        return 1
    print(f"test {result.kind.value} -> {result.target}")
    for d in result.devices:
        detail = f" ({d.error})" if d.error else ""
        print(f"  {d.device}: {OUTCOMES[d.outcome.value]}{detail}")
    return 0 if any(d.outcome.value == "sent" for d in result.devices) else 1


def check_packs() -> int:
    """Pack authoring aid: one line per pack, then its problems. Exit 1 if any is rejected."""
    rejected = 0
    for report in inspect_packs():
        state = "rejected" if report.pack is None else "ok"
        rejected += report.pack is None
        print(f"{report.dir.name}: {state}")
        for problem in report.errors:
            print(f"  error: {problem}")
        for problem in report.warnings:
            print(f"  warning: {problem}")
    return 1 if rejected else 0


def check_vault() -> int:
    """Opens vault.db with the keychain key (creating both on first run). Never prints values."""
    from runner.sanitize.vault_store import SqlCipherVault, VaultError, default_path

    try:
        with SqlCipherVault() as vault:
            print(f"vault: {default_path()} ({vault.count()} pseudonyms)")
    except VaultError as exc:
        print(f"vault: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="runner")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    sub.add_parser("vapid")
    sub.add_parser("packs")
    sub.add_parser("vault")
    test = sub.add_parser("notify-test", help="send a test Web Push to every device now")
    test.add_argument(
        "kind", nargs="?", default="day_ready", choices=[k.value for k in NotificationKind]
    )
    for name in ("run", "tick"):
        sub.add_parser(name).add_argument("--dry-run", action="store_true")
    trig = sub.add_parser("trigger")
    trig.add_argument("job", choices=[j.value for j in JobName])
    trig.add_argument("--dry-run", action="store_true")
    trig.add_argument(
        "--force",
        action="store_true",
        help="re-run the latest occurrence even if it succeeded (max 3 attempts)",
    )
    args = parser.parse_args(argv)

    configure_logging()
    if args.cmd == "login":
        return login()
    if args.cmd == "packs":
        return check_packs()
    if args.cmd == "vault":
        return check_vault()
    if args.cmd == "notify-test":
        return notify_test(args.kind)  # no instance lock: works while `run` is going
    if args.cmd == "vapid":
        private, public = generate_vapid_keys()
        print(f"QUESTBOARD_VAPID_PRIVATE_KEY={private}   # runner machine only (keep secret)")
        print(f"NEXT_PUBLIC_VAPID_PUBLIC_KEY={public}   # web app build")
        return 0
    try:
        with InstanceLock(data_dir() / "runner.lock"):
            scheduler = build(args.dry_run)
            loop = Loop(scheduler)
            if args.cmd == "run":
                loop.run_forever()
            elif args.cmd == "tick":
                loop.step(first=True)
            else:
                job = JobName(args.job)
                for d in scheduler.evaluate(Trigger.manual, only=job, force=args.force):
                    print(f"{d.job.value}: {d.action} ({d.reason})")
    except AlreadyRunning as exc:
        print(exc, file=sys.stderr)
        return EXIT_ALREADY_RUNNING
    except SettingsMissing as exc:
        print(exc, file=sys.stderr)
        return EXIT_NOT_SIGNED_IN
    return 0


if __name__ == "__main__":
    sys.exit(main())
