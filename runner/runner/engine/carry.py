"""daily_pm accounting: carry-over rules live in code (CLAUDE.md "Carry-over rules").

Unfinished daily quests move to tomorrow with carries + 1, up to 3 carries; hard-deadline
obligations always carry. Past the cap the quest is abandoned (the AM refresh sees carries = 3
first and may propose a split). Quests past their deadline become overdue.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from questboard_schema.quest_schema import Quest

MAX_CARRIES = {"daily": 3, "weekly": 2}
UNFINISHED = {"open", "in_progress", "snoozed", "deferred", "overdue"}


def carry_patch(q: Quest, today: date, now: datetime) -> dict[str, Any] | None:
    """The patch for one daily quest at end of day, or None when nothing changes."""
    if q.cadence.value != "daily" or q.status.value not in UNFINISHED:
        return None
    if q.scheduled_for is None or q.scheduled_for > today:
        return None  # deferred to a later day, or not on a board
    past_due = q.deadline is not None and q.deadline <= now
    if q.hard_deadline or q.carries < MAX_CARRIES["daily"]:
        return {
            "status": "overdue" if past_due else "open",
            "scheduled_for": (today + timedelta(days=1)).isoformat(),
            "carries": q.carries + 1,
            "snoozed_until": None,
        }
    return {"status": "abandoned", "snoozed_until": None}
