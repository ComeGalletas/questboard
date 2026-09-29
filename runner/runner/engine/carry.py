"""daily_pm accounting: carry-over rules live in code (CLAUDE.md "Carry-over rules").

Unfinished daily quests move to tomorrow with carries + 1, up to 3 carries; hard-deadline
obligations always carry. Past the cap the quest is abandoned (the AM refresh sees carries = 3
first and may propose a split). Quests past their deadline become overdue.

Forgotten (decided 2026-09-29) is an event, not a status: a daily quest that was never started on
its board day gets that day appended to `forgotten_on`, and still carries (or is abandoned) under
the rules above. The app fires the `forgotten` line and counts the day as a miss from that list.
Snoozed quests and quests deferred to a later day are not forgotten. Actual time is only logged
when a quest is finished (done / partial), which closes it, so an unfinished quest has none.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from questboard_schema.quest_schema import Quest

MAX_CARRIES = {"daily": 3, "weekly": 2, "monthly": 2}
UNFINISHED = {"open", "in_progress", "snoozed", "deferred", "overdue"}
UNTOUCHED = {"open", "deferred", "overdue"}  # deferred here = the day it was deferred to came


def forgotten(q: Quest, today: date, now: datetime) -> bool:
    """Never started on `today`: no start / in-progress and no snooze that day."""
    if q.status.value not in UNTOUCHED:
        return False
    return q.started_at is None or q.started_at.astimezone(now.tzinfo).date() != today


def _forgotten_patch(q: Quest, today: date, now: datetime) -> dict[str, Any]:
    days = list(q.forgotten_on or [])
    if not forgotten(q, today, now) or today in days:
        return {}
    return {"forgotten_on": [d.isoformat() for d in [*days, today]]}


def carry_patch(q: Quest, today: date, now: datetime) -> dict[str, Any] | None:
    """The patch for one daily quest at end of day, or None when nothing changes."""
    if q.cadence.value != "daily" or q.status.value not in UNFINISHED:
        return None
    if q.scheduled_for is None or q.scheduled_for > today:
        return None  # deferred to a later day, or not on a board
    past_due = q.deadline is not None and q.deadline <= now
    missed = _forgotten_patch(q, today, now)
    if q.hard_deadline or q.carries < MAX_CARRIES["daily"]:
        return {
            "status": "overdue" if past_due else "open",
            "scheduled_for": (today + timedelta(days=1)).isoformat(),
            "carries": q.carries + 1,
            "snoozed_until": None,
            **missed,
        }
    return {"status": "abandoned", "snoozed_until": None, **missed}


def period_carry_patch(q: Quest, next_start: date, now: datetime) -> dict[str, Any] | None:
    """Weekly/monthly quests left open when a new period starts move to it (cap per cadence)."""
    cadence = q.cadence.value
    if cadence == "daily" or q.status.value not in UNFINISHED:
        return None
    if q.scheduled_for is None or q.scheduled_for >= next_start:
        return None
    past_due = q.deadline is not None and q.deadline <= now
    if q.hard_deadline or q.carries < MAX_CARRIES[cadence]:
        return {
            "status": "overdue" if past_due else "open",
            "scheduled_for": next_start.isoformat(),
            "carries": q.carries + 1,
            "snoozed_until": None,
        }
    return {"status": "abandoned", "snoozed_until": None}
