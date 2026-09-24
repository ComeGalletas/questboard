"""Runner entry point.

  python -m runner login                     one-time: Supabase URL/key + sign in (keychain)
  python -m runner run [--dry-run]           trigger loop (start, 5-min tick, network up)
  python -m runner tick [--dry-run]          one evaluation, then exit
  python -m runner trigger JOB [--dry-run]   manual run of one job

--dry-run uses an in-memory DB with the default config. Output lists job decisions only,
never data.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sys

from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.config_schema import Config
from questboard_schema.llm_run_schema import Trigger

from runner.jobs import HANDLERS
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
    return Scheduler(repo=repo, handlers=HANDLERS, providers=providers_for(config))


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="runner")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    for name in ("run", "tick"):
        sub.add_parser(name).add_argument("--dry-run", action="store_true")
    trig = sub.add_parser("trigger")
    trig.add_argument("job", choices=[j.value for j in JobName])
    trig.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if args.cmd == "login":
        return login()
    try:
        with InstanceLock(data_dir() / "runner.lock"):
            scheduler = build(args.dry_run)
            loop = Loop(scheduler)
            if args.cmd == "run":
                loop.run_forever()
            elif args.cmd == "tick":
                loop.step(first=True)
            else:
                for d in scheduler.evaluate(Trigger.manual, only=JobName(args.job)):
                    print(f"{d.job.value}: {d.action} ({d.reason})")
    except (AlreadyRunning, SettingsMissing) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
