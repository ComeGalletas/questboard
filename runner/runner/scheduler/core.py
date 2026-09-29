"""The scheduler: decides which P0 jobs run on each trigger and records every LLM attempt.

Guards (CLAUDE.md "Scheduler rules"), checked in this order for LLM jobs:
  DB reachable -> slot window -> configured (planners only) -> idempotent per (job, slot, date)
  -> max 3 attempts -> retry backoff 5/15/60 min -> input freshness (2 h) -> a provider reachable.
Manual triggers skip the window, backoff and freshness guards, never setup, idempotency or the cap,
except that a forced manual trigger (`trigger JOB --force`) adds an attempt to an occurrence
that already succeeded (recorded with forced=true; still capped at MAX_ATTEMPTS, which the DB
enforces too).
"Not configured" (no goals yet) writes no llm_runs row, so the slot stays open for after setup.
Catch-up after boot / reconnect only ever looks at each job's most recent occurrence.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.config_schema import Config
from questboard_schema.llm_run_schema import LLMRun, Status, TokenUsage, Trigger

from runner.providers.base import Provider, ProviderError, ProviderOutputError
from runner.repo import Repo, RepoUnavailable
from runner.scheduler.schedule import (
    ORDER,
    SPECS,
    JobSpec,
    Occurrence,
    in_window,
    latest_occurrence,
)

log = logging.getLogger("questboard.runner")

MAX_ATTEMPTS = 3
BACKOFF = (timedelta(minutes=5), timedelta(minutes=15), timedelta(minutes=60))
FRESHNESS = timedelta(hours=2)
STALE_RUN = timedelta(minutes=30)
STALE_ERROR = "stale run"
DB_DOWN = "db unreachable"
FINISHED_BAD = {Status.failed, Status.invalid_output}
IN_FLIGHT = {Status.queued, Status.running}


@dataclass(frozen=True)
class JobContext:
    occurrence: Occurrence
    trigger: Trigger
    now: datetime  # local, aware
    config: Config
    repo: Repo
    providers: list[Provider]
    run_id: str | None = None  # the llm_runs row for this attempt


@dataclass(frozen=True)
class JobResult:
    provider: ProviderName | None = None
    tokens: TokenUsage | None = None
    # Planning jobs: how many diff ops were proposed, and the model's summary of them.
    ops_count: int | None = None
    summary: str | None = None


JobHandler = Callable[[JobContext], JobResult]


@dataclass(frozen=True)
class Decision:
    job: JobName
    action: Literal["run", "skip"]
    reason: str
    status: Status | None = None  # outcome when it ran


@dataclass
class Scheduler:
    repo: Repo
    handlers: Mapping[JobName, JobHandler]
    providers: Mapping[ProviderName, Provider] = field(default_factory=dict)
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    version: str = "0.0.0"
    # P2 step after the jobs (notifications). Gets (repo, config, local now).
    after_jobs: Callable[[Repo, Config, datetime], object] | None = None

    def evaluate(
        self, trigger: Trigger, only: JobName | None = None, force: bool = False
    ) -> list[Decision]:
        """One pass over the jobs. Never raises for job failures; returns what happened.

        `force` (manual only) re-runs an LLM job's latest occurrence even if it succeeded."""
        if force and trigger != Trigger.manual:
            raise ValueError("force is for manual triggers only")
        jobs = [j for j in ORDER if j in self.handlers and (only is None or j == only)]
        try:
            self.repo.ping()
            config = self.repo.get_config()
            state = self.repo.get_runner_state()
        except RepoUnavailable as exc:
            return [Decision(j, "skip", f"{DB_DOWN}: {exc}") for j in jobs]

        now = self.clock().astimezone(ZoneInfo(config.timezone))
        decisions = []
        for job in jobs:
            spec = SPECS[job]
            try:
                if spec.uses_llm:
                    decision = self._llm_job(spec, trigger, now, config, state, force)
                else:
                    decision = self._interval_job(spec, trigger, now, config, state)
                    state = self.repo.get_runner_state()
            except RepoUnavailable as exc:
                decision = Decision(job, "skip", f"{DB_DOWN}: {exc}")
            decisions.append(decision)
        if self.after_jobs is not None:
            try:
                self.after_jobs(self.repo, config, now)
            except RepoUnavailable:
                pass  # next tick
            except Exception as exc:  # noqa: BLE001 - never let notifications stop the loop
                log.warning("notifications failed: %s", type(exc).__name__)
        self._heartbeat(now, config)
        return decisions

    # -- jobs -------------------------------------------------------------------------------

    def _interval_job(self, spec, trigger, now, config, state) -> Decision:
        last = state.last_ingest_at if state else None
        if trigger != Trigger.manual and last and now - last < spec.every:
            return Decision(spec.name, "skip", "not due")
        occ = latest_occurrence(spec, now)
        ctx = JobContext(occ, trigger, now, config, self.repo, [])
        try:
            self.handlers[spec.name](ctx)
        except Exception as exc:  # noqa: BLE001 - a job failure must never stop the loop
            return Decision(spec.name, "run", f"failed: {type(exc).__name__}", Status.failed)
        self.repo.update_runner_state({"last_ingest_at": now.astimezone(UTC).isoformat()})
        return Decision(spec.name, "run", "ok", Status.succeeded)

    def _llm_job(self, spec: JobSpec, trigger, now, config, state, force=False) -> Decision:
        manual = trigger == Trigger.manual
        occ = latest_occurrence(spec, now)
        if not manual and not in_window(spec, occ, now):
            return Decision(spec.name, "skip", "outside slot window")
        if spec.needs_setup and not config.goals:
            return Decision(spec.name, "skip", "not configured (no goals; finish setup first)")

        runs = self.repo.list_runs(spec.name, occ.slot, occ.date)
        done_before = any(r.status == Status.succeeded for r in runs)
        if done_before and not force:
            return Decision(spec.name, "skip", "already done")
        for i, r in enumerate(runs):
            if r.status in IN_FLIGHT:
                if r.started_at and now - r.started_at < STALE_RUN:
                    return Decision(spec.name, "skip", "in progress")
                # The runner died mid-run (crash, sleep, power loss): count it as a failure.
                stale = {"status": Status.failed, "error": STALE_ERROR, "finished_at": now}
                self.repo.update_run(str(r.id), stale)
                runs[i] = r.model_copy(update=stale)
        if len(runs) >= MAX_ATTEMPTS:
            return Decision(spec.name, "skip", f"gave up after {MAX_ATTEMPTS} attempts")
        last = runs[-1] if runs else None
        # A stale run already waited out STALE_RUN; retry it without further backoff.
        if (
            not manual
            and last
            and last.status in FINISHED_BAD
            and last.finished_at
            and last.error != STALE_ERROR
        ):
            retry_at = last.finished_at + BACKOFF[last.attempt - 1]
            if now < retry_at:
                return Decision(spec.name, "skip", f"backoff until {retry_at:%H:%M}")
        if not manual and self._inputs_stale(config, state, now):
            return Decision(spec.name, "skip", "inputs stale (ingest older than 2 h)")
        providers = self._providers_for(config, spec.name)
        if spec.provider_required and not any(p.is_available() for p in providers):
            return Decision(spec.name, "skip", "no provider reachable")
        if done_before:
            # A forced re-run replaces the earlier attempts' unanswered proposals.
            self.repo.supersede_pending_proposals(spec.name, [str(r.id) for r in runs])
        return self._run(
            spec, occ, trigger, now, config, providers, attempt=len(runs) + 1, forced=done_before
        )

    def _run(self, spec, occ, trigger, now, config, providers, attempt, forced=False) -> Decision:
        run = self.repo.insert_run(
            LLMRun(
                job=spec.name,
                slot=occ.slot,
                date=occ.date,
                trigger=trigger,
                attempt=attempt,
                status=Status.running,
                forced=forced,
                started_at=now,
            )
        )
        ctx = JobContext(occ, trigger, now, config, self.repo, providers, run_id=str(run.id))
        try:
            result = self.handlers[spec.name](ctx)
        except ProviderOutputError as exc:
            return self._finish(spec, run, Status.invalid_output, str(exc))
        except ProviderError as exc:
            # ProviderError messages never contain prompt or response text.
            return self._finish(spec, run, Status.failed, str(exc))
        except Exception as exc:  # noqa: BLE001 - class name only: messages may carry data
            return self._finish(spec, run, Status.failed, type(exc).__name__)
        done = self.clock().astimezone(now.tzinfo)
        fields = {
            "status": Status.succeeded,
            "provider_used": result.provider,
            "tokens": result.tokens,
            "finished_at": done,
        }
        reason = "ok"
        if result.ops_count is not None:
            fields |= {"ops_count": result.ops_count, "summary": result.summary}
            reason = f"ok, {result.ops_count} ops"
            log.info("%s %s: %d ops proposed", spec.name.value, occ.date, result.ops_count)
        self.repo.update_run(str(run.id), fields)
        if spec.slot:
            key = "last_am_success" if spec.slot == "AM" else "last_pm_success"
            self.repo.update_runner_state({key: done.astimezone(UTC).isoformat()})
        return Decision(spec.name, "run", reason, Status.succeeded)

    def _finish(self, spec, run: LLMRun, status: Status, error: str) -> Decision:
        self.repo.update_run(
            str(run.id),
            {"status": status, "error": error[:500], "finished_at": self.clock()},
        )
        return Decision(spec.name, "run", error[:120], status)

    # -- guards and state -------------------------------------------------------------------

    def process_live(self) -> int:
        """P1: answer pending live requests (setup assistant, ...). Called between ticks."""
        from runner.live import process_live

        try:
            config = self.repo.get_config()
            providers = [self.providers[n] for n in config.llm.providers if n in self.providers]
            return process_live(self.repo, config, providers, self.clock())
        except RepoUnavailable:
            return 0

    def _providers_for(self, config: Config, job: JobName) -> list[Provider]:
        per_job = (config.llm.per_job or {}).get(job)
        order = per_job.root if per_job else config.llm.providers
        return [self.providers[name] for name in order if name in self.providers]

    @staticmethod
    def _inputs_stale(config: Config, state, now: datetime) -> bool:
        if not (config.integrations.gmail or config.integrations.gcal):
            return False  # nothing to ingest, nothing to be stale
        last = state.last_ingest_at if state else None
        return last is None or now - last > FRESHNESS

    def _heartbeat(self, now: datetime, config: Config) -> None:
        checked = now.astimezone(UTC).isoformat()
        health = {
            name.value: {"reachable": p.is_available(), "checked_at": checked}
            for name, p in self.providers.items()
        }
        with contextlib.suppress(RepoUnavailable):  # next tick retries
            self.repo.update_runner_state(
                {"heartbeat_at": checked, "provider_health": health, "runner_version": self.version}
            )
