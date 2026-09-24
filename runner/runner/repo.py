"""What the runner reads and writes in the cloud DB. Pseudonymized data only (invariant 5).

`Repo` is the interface; `MemoryRepo` backs tests and `--dry-run`. The Supabase implementation
talks to PostgREST as the signed-in user, so RLS applies to the runner like any other client.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Protocol

from questboard_schema.common_schema import JobName
from questboard_schema.config_schema import Config
from questboard_schema.llm_run_schema import LLMRun
from questboard_schema.quest_schema import Quest
from questboard_schema.runner_state_schema import RunnerState

ACTIVE = ("open", "in_progress", "snoozed", "deferred", "overdue")


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
    def list_quests(self, since: date) -> list[Quest]:
        """Active quests plus everything scheduled on or after `since`."""
        ...

    def update_quest(self, quest_id: str, fields: dict[str, Any]) -> None: ...
    def list_feedback(self, since: date) -> list[dict[str, Any]]: ...
    def supersede_pending_proposals(self) -> int: ...
    def insert_proposals(self, rows: list[dict[str, Any]]) -> None: ...
    def replace_quest_lines(self, quest_ids: list[str], rows: list[dict[str, Any]]) -> None:
        """Drop unused cached lines for these quests, then insert `rows`."""
        ...

    def replace_board_lines(self, rows: list[dict[str, Any]]) -> None:
        """Drop unused board-level lines (quest_id null), then insert `rows`."""
        ...

    def insert_notifications(self, rows: list[dict[str, Any]]) -> None:
        """Insert, silently skipping rows that hit the (kind, target, dedup_date) key."""
        ...

    def list_undelivered_notifications(self, since: datetime) -> list[dict[str, Any]]: ...
    def mark_notifications_sent(self, ids: list[str], at: datetime) -> None: ...
    def list_push_subscriptions(self) -> list[dict[str, Any]]: ...
    def delete_push_subscription(self, sub_id: str) -> None: ...


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
        self.quests: list[Quest] = []
        self.feedback: list[dict[str, Any]] = []
        self.proposals: list[dict[str, Any]] = []
        self.lines: list[dict[str, Any]] = []
        self.notifications: list[dict[str, Any]] = []
        self.clock = lambda: datetime.now().astimezone()  # stands in for the DB's now()
        self.push_subscriptions: list[dict[str, Any]] = []

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

    def list_quests(self, since: date) -> list[Quest]:
        self._check()
        return [
            q
            for q in self.quests
            if q.status.value in ACTIVE or (q.scheduled_for and q.scheduled_for >= since)
        ]

    def update_quest(self, quest_id: str, fields: dict[str, Any]) -> None:
        self._check()
        for i, q in enumerate(self.quests):
            if str(q.id) == str(quest_id):
                self.quests[i] = Quest.model_validate({**q.model_dump(), **fields})
                return
        raise KeyError(quest_id)

    def list_feedback(self, since: date) -> list[dict[str, Any]]:
        self._check()
        return [f for f in self.feedback if f["created_at"][:10] >= since.isoformat()]

    def supersede_pending_proposals(self) -> int:
        self._check()
        pending = [p for p in self.proposals if p["status"] == "pending"]
        for p in pending:
            p["status"] = "superseded"
        return len(pending)

    def insert_proposals(self, rows: list[dict[str, Any]]) -> None:
        self._check()
        self.proposals.extend({"id": str(uuid.uuid4()), "status": "pending", **r} for r in rows)

    def replace_quest_lines(self, quest_ids: list[str], rows: list[dict[str, Any]]) -> None:
        self._check()
        ids = {str(i) for i in quest_ids}
        self.lines = [
            line
            for line in self.lines
            if not (str(line.get("quest_id")) in ids and line.get("used_at") is None)
        ]
        self.lines.extend(rows)

    def replace_board_lines(self, rows: list[dict[str, Any]]) -> None:
        self._check()
        self.lines = [
            line
            for line in self.lines
            if not (line.get("quest_id") is None and line.get("used_at") is None)
        ]
        self.lines.extend(rows)

    def insert_notifications(self, rows: list[dict[str, Any]]) -> None:
        self._check()
        seen = {(n["kind"], n["target"], n["dedup_date"]) for n in self.notifications}
        for r in rows:
            key = (r["kind"], r["target"], r["dedup_date"])
            if key not in seen:
                seen.add(key)
                self.notifications.append(
                    {
                        "id": str(uuid.uuid4()),
                        "sent_at": None,
                        "created_at": self.clock(),
                        **r,
                    }
                )

    def list_undelivered_notifications(self, since: datetime) -> list[dict[str, Any]]:
        self._check()
        return [n for n in self.notifications if n["sent_at"] is None and n["created_at"] >= since]

    def mark_notifications_sent(self, ids: list[str], at: datetime) -> None:
        self._check()
        for n in self.notifications:
            if n["id"] in ids:
                n["sent_at"] = at

    def list_push_subscriptions(self) -> list[dict[str, Any]]:
        self._check()
        return list(self.push_subscriptions)

    def delete_push_subscription(self, sub_id: str) -> None:
        self._check()
        self.push_subscriptions = [s for s in self.push_subscriptions if s["id"] != sub_id]
