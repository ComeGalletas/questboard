from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.config_schema import Config
from questboard_schema.llm_run_schema import Status, TokenUsage, Trigger

from runner.providers.base import (
    GenerationRequest,
    Provider,
    ProviderError,
    ProviderOutputError,
    RawCompletion,
)
from runner.repo import MemoryRepo
from runner.scheduler.core import JobContext, JobResult, Scheduler
from runner.scheduler.loop import Loop
from runner.scheduler.schedule import SPECS, in_window, latest_occurrence

BOGOTA = ZoneInfo("America/Bogota")

CONFIG = Config.model_validate(
    {
        "timezone": "America/Bogota",
        "goals": [{"id": "g1", "title": "Run a 10k", "horizon": "quarter"}],
        "capacity": {"weekday_hours": 3, "weekend_hours": 5, "focus_factor": 0.7},
        "quiet_hours": {"start": "22:00", "end": "07:00"},
        "xp_weights": {},
        "llm": {"providers": ["claude-cli", "ollama"]},
        "persona_order": ["coach"],
        "integrations": {"gmail": False, "gcal": False},
        "features": {"three_d": False, "mobile_rehydration": False},
        "notifications": {"persona_speech_per_day": 2, "persona_speech_on_mobile": False},
    }
)


def local(y: int, mo: int, d: int, h: int, mi: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=BOGOTA)


class Clock:
    def __init__(self, at: datetime):
        self.at = at

    def __call__(self) -> datetime:
        return self.at.astimezone(UTC)

    def advance(self, **kw: Any) -> None:
        self.at += timedelta(**kw)


class FakeProvider(Provider):
    def __init__(self, name: ProviderName, available: bool = True):
        self.name = name  # type: ignore[misc]
        self.available = available

    def is_available(self) -> bool:
        return self.available

    def _complete(self, request: GenerationRequest, schema: dict[str, Any]) -> RawCompletion:
        raise NotImplementedError


@dataclass
class Handler:
    """Records calls; raises `fail` if set."""

    fail: Exception | None = None
    calls: int = 0

    def __call__(self, ctx: JobContext) -> JobResult:
        self.calls += 1
        if self.fail:
            raise self.fail
        return JobResult(ProviderName.claude_cli, TokenUsage(input=100, output=20))


def make(at: datetime, **handlers: Handler) -> tuple[Scheduler, MemoryRepo, Clock]:
    repo = MemoryRepo(CONFIG)
    clock = Clock(at)
    sched = Scheduler(
        repo=repo,
        handlers={JobName(k): v for k, v in handlers.items()},
        providers={
            ProviderName.claude_cli: FakeProvider(ProviderName.claude_cli),
            ProviderName.ollama: FakeProvider(ProviderName.ollama),
        },
        clock=clock,
        version="test",
    )
    return sched, repo, clock


# -- schedule -----------------------------------------------------------------------------


def test_latest_occurrences() -> None:
    now = local(2026, 9, 25, 4, 0)  # Friday before the AM slot
    am = latest_occurrence(SPECS[JobName.daily_am], now)
    assert am.date.isoformat() == "2026-09-24"
    assert not in_window(SPECS[JobName.daily_am], am, now)
    at_six = local(2026, 9, 25, 6, 0)
    am = latest_occurrence(SPECS[JobName.daily_am], at_six)
    assert (am.date.isoformat(), am.slot) == ("2026-09-25", "AM")
    assert in_window(SPECS[JobName.daily_am], am, at_six)
    weekly = latest_occurrence(SPECS[JobName.weekly], now)
    assert weekly.scheduled_at == local(2026, 9, 20, 18, 0)  # last Sunday
    monthly = latest_occurrence(SPECS[JobName.monthly], local(2026, 10, 1, 7, 0))
    assert monthly.scheduled_at == local(2026, 9, 1, 8, 0)


# -- guards -------------------------------------------------------------------------------


def test_daily_am_runs_once_in_its_window_and_records_the_run() -> None:
    h = Handler()
    sched, repo, clock = make(local(2026, 9, 25, 5, 35), daily_am=h)
    [d] = sched.evaluate(Trigger.tick)
    assert (d.action, d.status) == ("run", Status.succeeded)
    [run] = repo.runs
    assert (run.slot.value, run.attempt, run.status) == ("AM", 1, Status.succeeded)
    assert run.provider_used == ProviderName.claude_cli
    assert repo.state["last_am_success"] is not None
    clock.advance(minutes=5)
    assert sched.evaluate(Trigger.tick)[0].reason == "already done"
    assert h.calls == 1


def test_outside_window_skips_unless_manual() -> None:
    h = Handler()
    sched, _, _ = make(local(2026, 9, 25, 13, 0), daily_am=h)
    assert sched.evaluate(Trigger.tick)[0].reason == "outside slot window"
    assert sched.evaluate(Trigger.manual)[0].status == Status.succeeded


def test_boot_catch_up_runs_only_the_most_recent_missed_slot() -> None:
    # PC off all weekend, booted Monday 08:00: today's AM runs; Sunday's PM is gone.
    am, pm, weekly = Handler(), Handler(), Handler()
    sched, repo, _ = make(local(2026, 9, 28, 8, 0), daily_am=am, daily_pm=pm, weekly=weekly)
    decisions = {d.job: d for d in sched.evaluate(Trigger.start)}
    assert decisions[JobName.daily_am].status == Status.succeeded
    assert decisions[JobName.daily_pm].reason == "outside slot window"
    assert decisions[JobName.weekly].status == Status.succeeded
    assert {r.date.isoformat() for r in repo.runs if r.job == JobName.weekly} == {"2026-09-27"}


def test_failures_back_off_then_give_up_after_three_attempts() -> None:
    h = Handler(fail=ProviderError("exited with code 1"))
    sched, repo, clock = make(local(2026, 9, 25, 6, 0), daily_am=h)
    assert sched.evaluate(Trigger.tick)[0].status == Status.failed
    clock.advance(minutes=4)
    assert sched.evaluate(Trigger.tick)[0].reason.startswith("backoff until")
    clock.advance(minutes=1)
    assert sched.evaluate(Trigger.tick)[0].status == Status.failed  # attempt 2
    clock.advance(minutes=14)
    assert sched.evaluate(Trigger.tick)[0].reason.startswith("backoff")
    clock.advance(minutes=1)
    assert sched.evaluate(Trigger.tick)[0].status == Status.failed  # attempt 3
    clock.advance(hours=2)
    assert sched.evaluate(Trigger.manual)[0].reason == "gave up after 3 attempts"
    assert [r.attempt for r in repo.runs] == [1, 2, 3]
    assert repo.runs[0].error == "exited with code 1"


def test_invalid_output_is_recorded_as_such() -> None:
    h = Handler(fail=ProviderOutputError("output failed validation after retry (2 errors)"))
    sched, repo, _ = make(local(2026, 9, 25, 6, 0), daily_am=h)
    assert sched.evaluate(Trigger.tick)[0].status == Status.invalid_output


def test_unexpected_errors_record_the_class_name_only() -> None:
    h = Handler(fail=ValueError("PERSON_7 said something private"))
    sched, repo, _ = make(local(2026, 9, 25, 6, 0), daily_am=h)
    sched.evaluate(Trigger.tick)
    assert repo.runs[0].error == "ValueError"


def test_manual_trigger_skips_backoff() -> None:
    h = Handler(fail=ProviderError("boom"))
    sched, repo, clock = make(local(2026, 9, 25, 6, 0), daily_am=h)
    sched.evaluate(Trigger.tick)
    h.fail = None
    clock.advance(minutes=1)
    assert sched.evaluate(Trigger.manual)[0].status == Status.succeeded


def test_stale_running_row_counts_as_a_failed_attempt() -> None:
    h = Handler()
    sched, repo, clock = make(local(2026, 9, 25, 6, 0), daily_am=h)
    from questboard_schema.llm_run_schema import LLMRun

    repo.insert_run(
        LLMRun(
            job=JobName.daily_am,
            slot="AM",
            date=clock.at.date(),
            trigger=Trigger.tick,
            attempt=1,
            status=Status.running,
            started_at=clock.at,
        )
    )
    assert sched.evaluate(Trigger.tick)[0].reason == "in progress"
    clock.advance(minutes=31)
    d = sched.evaluate(Trigger.tick)[0]
    assert d.status == Status.succeeded
    assert [(r.attempt, r.status) for r in repo.runs] == [
        (1, Status.failed),
        (2, Status.succeeded),
    ]


def test_force_adds_attempts_to_a_succeeded_occurrence_up_to_the_cap() -> None:
    h = Handler()
    sched, repo, clock = make(local(2026, 9, 28, 8, 0), weekly=h)  # catch-up of Sunday 09-27
    assert sched.evaluate(Trigger.start)[0].status == Status.succeeded
    [first] = repo.runs
    daily_run = repo.insert_run(first.model_copy(update={"job": JobName.daily_am, "slot": "AM"}))
    repo.proposals = [
        {"id": "p1", "run_id": str(first.id), "status": "pending", "op": "add"},
        {"id": "p2", "run_id": str(daily_run.id), "status": "pending", "op": "add"},
    ]
    assert sched.evaluate(Trigger.manual)[0].reason == "already done"
    with pytest.raises(ValueError):
        sched.evaluate(Trigger.tick, force=True)

    d = sched.evaluate(Trigger.manual, force=True)[0]
    assert d.status == Status.succeeded
    weekly_runs = [r for r in repo.runs if r.job == JobName.weekly]
    assert [(r.attempt, r.trigger, r.forced) for r in weekly_runs] == [
        (1, Trigger.start, False),
        (2, Trigger.manual, True),
    ]
    # Only the earlier weekly attempt's proposals give way; daily_am's stay pending.
    assert [p["status"] for p in repo.proposals] == ["superseded", "pending"]
    assert sched.evaluate(Trigger.tick)[0].reason == "already done"  # scheduled runs stay put
    for _ in range(8):  # forced attempts go up to MAX_FORCED_ATTEMPTS, not MAX_ATTEMPTS
        clock.advance(minutes=1)
        assert sched.evaluate(Trigger.manual, force=True)[0].status == Status.succeeded
    assert sched.evaluate(Trigger.manual, force=True)[0].reason == "gave up after 10 attempts"
    assert h.calls == 10
    assert [r.attempt for r in repo.runs if r.job == JobName.weekly] == list(range(1, 11))


def test_force_on_an_occurrence_without_a_success_is_a_normal_manual_run() -> None:
    sched, repo, _ = make(local(2026, 9, 28, 8, 0), weekly=Handler())
    assert sched.evaluate(Trigger.manual, force=True)[0].status == Status.succeeded
    assert repo.runs[0].forced is False


def test_planning_runs_record_op_count_and_summary() -> None:
    sched, repo, _ = make(local(2026, 9, 28, 8, 0))
    sched.handlers = {
        JobName.weekly: lambda ctx: JobResult(
            ProviderName.claude_cli, ops_count=0, summary="Both goals already have open quests."
        )
    }
    [d] = sched.evaluate(Trigger.start)
    assert (d.status, d.reason) == (Status.succeeded, "ok, 0 ops")
    [run] = repo.runs
    assert (run.ops_count, run.summary) == (0, "Both goals already have open quests.")


def test_manual_daily_am_before_the_slot_plans_today() -> None:
    sched, repo, _ = make(local(2026, 9, 29, 3, 0), daily_am=Handler())
    assert sched.evaluate(Trigger.tick)[0].reason == "outside slot window"
    assert sched.evaluate(Trigger.manual)[0].status == Status.succeeded
    assert [r.date.isoformat() for r in repo.runs] == ["2026-09-29"]  # not yesterday's slot


def replan_request(job: str, rid: str = "r1", at: datetime | None = None) -> dict[str, Any]:
    created = (at or local(2026, 9, 29, 9, 0)) - timedelta(seconds=5)
    return {
        "id": rid,
        "kind": "replan",
        "status": "pending",
        "created_at": created,
        "payload": {"job": job},
    }


def test_replan_requests_run_forced_planning_jobs() -> None:
    def weekly(ctx: JobContext) -> JobResult:
        return JobResult(ProviderName.claude_cli, ops_count=len(ctx.repo.runs) - 1)

    sched, repo, clock = make(local(2026, 9, 29, 9, 0))
    sched.handlers = {JobName.weekly: weekly}
    assert sched.evaluate(Trigger.tick)[0].status == Status.succeeded  # the week is planned
    repo.requests = [replan_request("weekly")]

    assert sched.process_live() == 1
    [req] = repo.requests
    assert req["status"] == "done"
    assert req["result"] == {"status": "succeeded", "reason": "ok, 1 ops", "ops_count": 1}
    assert [(r.attempt, r.trigger, r.forced) for r in repo.runs][-1] == (2, Trigger.manual, True)


def test_replan_failures_carry_the_scheduler_reason_and_wait_for_a_provider() -> None:
    h = Handler(fail=ProviderError("exited with code 1"))
    sched, repo, _ = make(local(2026, 9, 29, 9, 0), daily_am=h)
    for p in sched.providers.values():
        p.available = False  # type: ignore[attr-defined]
    repo.requests = [replan_request("daily_am")]
    assert sched.process_live() == 0
    assert repo.requests[0]["status"] == "pending"  # P1 waits; the app shows "pending"

    for p in sched.providers.values():
        p.available = True  # type: ignore[attr-defined]
    sched.process_live()
    req = repo.requests[0]
    assert (req["status"], req["error"]) == ("failed", "exited with code 1")
    assert req["result"]["status"] == "failed"

    repo.requests = [replan_request("persona_digest", rid="r2")]  # not a planning job
    sched.process_live()
    assert (repo.requests[0]["status"], repo.requests[0]["error"]) == ("failed", "ValidationError")


def test_no_provider_reachable() -> None:
    h = Handler()
    sched, _, _ = make(local(2026, 9, 25, 6, 0), daily_am=h)
    for p in sched.providers.values():
        p.available = False  # type: ignore[attr-defined]
    assert sched.evaluate(Trigger.tick)[0].reason == "no provider reachable"
    assert h.calls == 0


def test_per_job_provider_override() -> None:
    sched, repo, _ = make(local(2026, 9, 25, 6, 0))
    data = CONFIG.model_dump(mode="json")
    data["llm"]["per_job"] = {"daily_am": ["ollama"]}
    repo.config = Config.model_validate(data)
    sched.providers[ProviderName.ollama].available = False  # type: ignore[attr-defined]
    seen: list[list[ProviderName]] = []
    sched.handlers = {
        JobName.daily_am: lambda ctx: seen.append([p.name for p in ctx.providers]) or JobResult()
    }
    assert sched.evaluate(Trigger.tick)[0].reason == "no provider reachable"
    sched.providers[ProviderName.ollama].available = True  # type: ignore[attr-defined]
    sched.evaluate(Trigger.tick)
    assert seen == [[ProviderName.ollama]]


def test_stale_inputs_block_llm_jobs_when_integrations_are_on() -> None:
    h, ingest = Handler(), Handler()
    sched, repo, clock = make(local(2026, 9, 25, 6, 0), daily_am=h)
    repo.config = Config.model_validate(
        {**CONFIG.model_dump(mode="json"), "integrations": {"gmail": True, "gcal": False}}
    )
    assert sched.evaluate(Trigger.tick)[0].reason == "inputs stale (ingest older than 2 h)"
    sched.handlers = {JobName.ingest: ingest, JobName.daily_am: h}
    decisions = sched.evaluate(Trigger.tick)
    assert [d.job for d in decisions] == [JobName.ingest, JobName.daily_am]
    assert decisions[1].status == Status.succeeded
    clock.advance(minutes=10)
    assert sched.evaluate(Trigger.tick)[0].reason == "not due"
    assert ingest.calls == 1


def test_planners_wait_for_setup_without_recording_a_run() -> None:
    # 2026-09-29 incident: the first tick on a fresh install planned the week against the
    # seeded config (no goals) and closed the slot, so a manual run after setup said
    # "already done". Planners now skip with no llm_runs row; daily_pm (code only) still runs.
    from runner.__main__ import DEFAULT_CONFIG  # same row as supabase default_config()

    am, pm, weekly, monthly = Handler(), Handler(), Handler(), Handler()
    sched, repo, clock = make(
        local(2026, 9, 28, 8, 0), daily_am=am, daily_pm=pm, weekly=weekly, monthly=monthly
    )
    repo.config = Config.model_validate(DEFAULT_CONFIG)
    decisions = {d.job: d for d in sched.evaluate(Trigger.start)}
    for job in (JobName.daily_am, JobName.weekly, JobName.monthly):
        assert decisions[job].reason == "not configured (no goals; finish setup first)"
    assert sched.evaluate(Trigger.manual, only=JobName.weekly)[0].reason.startswith(
        "not configured"
    )
    assert repo.runs == [] and am.calls == weekly.calls == monthly.calls == 0

    clock.advance(hours=13, minutes=30)  # 21:30, PM slot: accounting needs no setup
    [d] = sched.evaluate(Trigger.tick, only=JobName.daily_pm)
    assert d.status == Status.succeeded and pm.calls == 1

    # The user finishes setup; the manual run seeds the week that started on Sunday's slot.
    repo.config = CONFIG
    [d] = sched.evaluate(Trigger.manual, only=JobName.weekly)
    assert d.status == Status.succeeded
    [run] = [r for r in repo.runs if r.job == JobName.weekly]
    assert (run.date.isoformat(), run.attempt) == ("2026-09-27", 1)
    # Idempotency still holds for manual triggers once the slot has succeeded.
    assert sched.evaluate(Trigger.manual, only=JobName.weekly)[0].reason == "already done"
    assert weekly.calls == 1


def test_db_outage_skips_everything_then_network_up_recovers() -> None:
    h = Handler()
    sched, repo, clock = make(local(2026, 9, 25, 6, 0), daily_am=h)
    loop = Loop(sched, sleep=lambda s: None)
    repo.online = False
    assert loop.step(first=True)[0].reason == "db unreachable: offline"
    repo.online = True
    clock.advance(minutes=5)
    decisions = loop.step()
    assert decisions[0].status == Status.succeeded
    assert repo.runs[0].trigger == Trigger.network_up


def test_heartbeat_records_provider_health() -> None:
    sched, repo, _ = make(local(2026, 9, 25, 13, 0))
    sched.providers[ProviderName.ollama].available = False  # type: ignore[attr-defined]
    sched.evaluate(Trigger.tick)
    assert repo.state["heartbeat_at"] is not None
    assert repo.state["provider_health"]["ollama"]["reachable"] is False
    assert repo.state["runner_version"] == "test"


def test_loop_survives_a_crashing_evaluate() -> None:
    sched, _, _ = make(local(2026, 9, 25, 13, 0))

    def boom(*_: Any, **__: Any) -> list:
        raise RuntimeError("secret detail")

    sched.evaluate = boom  # type: ignore[method-assign]
    Loop(sched, sleep=lambda s: None).run_forever(ticks=2)


def test_instance_lock(tmp_path) -> None:
    from runner.scheduler.lock import AlreadyRunning, InstanceLock

    path = tmp_path / "runner.lock"
    with InstanceLock(path), pytest.raises(AlreadyRunning):
        InstanceLock(path).acquire()
    with InstanceLock(path):
        pass


def test_cli_dry_run_tick(tmp_path, monkeypatch, capsys) -> None:
    from runner.__main__ import main

    monkeypatch.setenv("QUESTBOARD_DATA_DIR", str(tmp_path))
    assert main(["trigger", "ingest", "--dry-run"]) == 0
    assert "ingest: run (ok)" in capsys.readouterr().out


def test_cli_exit_codes_for_the_desktop_shell(tmp_path, monkeypatch, capsys) -> None:
    from runner.__main__ import EXIT_ALREADY_RUNNING, EXIT_NOT_SIGNED_IN, main
    from runner.scheduler.lock import InstanceLock

    monkeypatch.setenv("QUESTBOARD_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("QUESTBOARD_SUPABASE_URL", raising=False)
    monkeypatch.delenv("QUESTBOARD_SUPABASE_ANON_KEY", raising=False)
    assert main(["tick"]) == EXIT_NOT_SIGNED_IN  # no runner.json in this data dir
    assert "runner login" in capsys.readouterr().err

    with InstanceLock(tmp_path / "runner.lock"):
        assert main(["tick", "--dry-run"]) == EXIT_ALREADY_RUNNING
    assert "another runner" in capsys.readouterr().err
    assert (EXIT_ALREADY_RUNNING, EXIT_NOT_SIGNED_IN) == (3, 4)  # runner.rs matches on these


def test_cli_trigger_force_is_passed_through(tmp_path, monkeypatch, capsys) -> None:
    from runner.__main__ import main

    seen: list[tuple[Trigger, JobName | None, bool]] = []

    def evaluate(self, trigger, only=None, force=False):
        seen.append((trigger, only, force))
        return []

    monkeypatch.setenv("QUESTBOARD_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(Scheduler, "evaluate", evaluate)
    assert main(["trigger", "weekly", "--dry-run", "--force"]) == 0
    assert main(["trigger", "weekly", "--dry-run"]) == 0
    assert seen == [
        (Trigger.manual, JobName.weekly, True),
        (Trigger.manual, JobName.weekly, False),
    ]


def test_providers_use_models_from_config() -> None:
    from runner.__main__ import DEFAULT_CONFIG, providers_for

    data = {**DEFAULT_CONFIG, "llm": {**DEFAULT_CONFIG["llm"], "models": {"ollama": "llama3.1"}}}
    built = providers_for(Config.model_validate(data))
    assert built[ProviderName.ollama].model == "llama3.1"  # type: ignore[attr-defined]
    assert built[ProviderName.claude_api].model == "claude-opus-5"  # type: ignore[attr-defined]
    assert built[ProviderName.claude_cli].model is None  # type: ignore[attr-defined]
