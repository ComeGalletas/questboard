"""What the runner reads and writes in the cloud DB. Pseudonymized data only (invariant 5).

`Repo` is the interface; `MemoryRepo` backs tests and `--dry-run`. The Supabase implementation
talks to PostgREST as the signed-in user, so RLS applies to the runner like any other client.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Protocol

from questboard_schema.common_schema import JobName
from questboard_schema.config_schema import Config
from questboard_schema.llm_run_schema import LLMRun
from questboard_schema.runner_state_schema import RunnerState


class RepoUnavailable(Exception):
    """The DB can't be reached right now (offline, auth expired, 5xx)."""


class Repo(Protocol):
    def ping(self) -> None: ...
    def get_config(self) -> Config: ...
    def get_runner_state(self) -> RunnerState | None: ...
    def update_runner_state(self, fields: dict[str, Any]) -> None: ...
    def list_runs(self, job: JobName, slot: str | None, day: date) -> list[LLMRun]: ...
    def insert_run(self, run: LLMRun) -> LLMRun: ...
    def update_run(self, run_id: str, fields: dict[str, Any]) -> None: ...


class MemoryRepo:
    """In-process stand-in for the cloud DB."""

    def __init__(self, config: Config, user_id: str = "00000000-0000-4000-8000-000000000001"):
        self.config = config
        self.user_id = user_id
        self.online = True
        self.state: dict[str, Any] = {
            "user_id": user_id,
            "heartbeat_at": None,
            "last_am_success": None,
            "last_pm_success": None,
            "last_ingest_at": None,
            "provider_health": {},
        }
        self.runs: list[LLMRun] = []

    def _check(self) -> None:
        if not self.online:
            raise RepoUnavailable("offline")

    def ping(self) -> None:
        self._check()

    def get_config(self) -> Config:
        self._check()
        return self.config

    def get_runner_state(self) -> RunnerState | None:
        self._check()
        return RunnerState.model_validate(self.state)

    def update_runner_state(self, fields: dict[str, Any]) -> None:
        self._check()
        self.state.update(fields)

    def list_runs(self, job: JobName, slot: str | None, day: date) -> list[LLMRun]:
        self._check()
        return sorted(
            (
                r
                for r in self.runs
                if r.job == job and (r.slot.value if r.slot else None) == slot and r.date == day
            ),
            key=lambda r: r.attempt,
        )

    def insert_run(self, run: LLMRun) -> LLMRun:
        self._check()
        stored = run.model_copy(update={"id": uuid.uuid4()})
        self.runs.append(stored)
        return stored

    def update_run(self, run_id: str, fields: dict[str, Any]) -> None:
        self._check()
        for i, r in enumerate(self.runs):
            if str(r.id) == str(run_id):
                self.runs[i] = LLMRun.model_validate({**r.model_dump(), **fields})
                return
        raise KeyError(run_id)
