"""When each job is due (CLAUDE.md "Scheduler rules"). Pure functions over local time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from questboard_schema.common_schema import JobName

Slot = Literal["AM", "PM"]


@dataclass(frozen=True)
class JobSpec:
    name: JobName
    kind: Literal["interval", "daily", "weekly", "monthly"]
    uses_llm: bool
    at: time | None = None
    weekday: int | None = None  # Monday = 0
    slot: Slot | None = None
    window: tuple[time, time] | None = None  # inclusive local-time window for the slot
    every: timedelta | None = None
    needs_provider: bool | None = None  # default: same as uses_llm

    @property
    def provider_required(self) -> bool:
        return self.uses_llm if self.needs_provider is None else self.needs_provider


SPECS: dict[JobName, JobSpec] = {
    JobName.ingest: JobSpec(JobName.ingest, "interval", False, every=timedelta(minutes=30)),
    JobName.daily_am: JobSpec(
        JobName.daily_am,
        "daily",
        True,
        at=time(5, 30),
        slot="AM",
        window=(time(5, 0), time(11, 59, 59)),
    ),
    # daily_pm is bookkept like an LLM job (slot, idempotency, backoff) but its accounting
    # is pure code, so it must not wait for a model (P0 is never blocked).
    JobName.daily_pm: JobSpec(
        JobName.daily_pm,
        "daily",
        True,
        at=time(21, 0),
        slot="PM",
        window=(time(17, 0), time(23, 59, 59)),
        needs_provider=False,
    ),
    JobName.weekly: JobSpec(JobName.weekly, "weekly", True, at=time(18, 0), weekday=6),
    JobName.monthly: JobSpec(JobName.monthly, "monthly", True, at=time(8, 0)),
    JobName.persona_digest: JobSpec(
        JobName.persona_digest, "weekly", True, at=time(17, 0), weekday=6
    ),
}

# P0 order inside one tick: fresh inputs first, then the day, then longer horizons.
ORDER: list[JobName] = [
    JobName.ingest,
    JobName.daily_am,
    JobName.daily_pm,
    JobName.weekly,
    JobName.monthly,
    JobName.persona_digest,
]


@dataclass(frozen=True)
class Occurrence:
    job: JobName
    slot: Slot | None
    date: date
    scheduled_at: datetime  # aware, local zone


def latest_occurrence(spec: JobSpec, now: datetime) -> Occurrence:
    """The most recent scheduled time at or before `now` (catch-up only ever looks at this one)."""
    if spec.kind == "interval":
        return Occurrence(spec.name, None, now.date(), now)
    assert spec.at is not None
    candidate = now.replace(hour=spec.at.hour, minute=spec.at.minute, second=0, microsecond=0)
    if spec.kind == "daily":
        if candidate > now:
            candidate -= timedelta(days=1)
    elif spec.kind == "weekly":
        assert spec.weekday is not None
        candidate -= timedelta(days=(candidate.weekday() - spec.weekday) % 7)
        if candidate > now:
            candidate -= timedelta(days=7)
    else:  # monthly, on the 1st
        candidate = candidate.replace(day=1)
        if candidate > now:
            prev = candidate - timedelta(days=1)
            candidate = candidate.replace(year=prev.year, month=prev.month)
    return Occurrence(spec.name, spec.slot, candidate.date(), candidate)


def in_window(spec: JobSpec, occ: Occurrence, now: datetime) -> bool:
    """Daily slots only run inside their window on their own date; other jobs have no window."""
    if spec.window is None:
        return True
    start, end = spec.window
    return now.date() == occ.date and start <= now.time() <= end
