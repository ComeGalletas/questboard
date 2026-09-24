"""Which notifications are due (CLAUDE.md "Notifications"). Pure code (P2), no model.

v1 kinds: day_ready, day_recap, quest_due, quest_overdue, streak_risk. Each carries a
questboard:// target and a persona; the DB dedups by (kind, target, date). Delivery waits
for quiet hours to end (see `deliverable`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from questboard_schema.config_schema import Config
from questboard_schema.quest_schema import Quest

ACTIVE = {"open", "in_progress", "snoozed", "deferred", "overdue"}
FINISHED = {"done", "partial"}
DUE_SOON = timedelta(hours=2)
STREAK_CHECK = time(19, 0)
TITLE_MAX, BODY_MAX = 80, 280


@dataclass(frozen=True)
class Notice:
    kind: str
    target: str
    persona: str | None
    title: str
    body: str
    channels: tuple[str, ...] = ("pc", "push")

    def row(self, day: date) -> dict:
        return {
            "kind": self.kind,
            "target": self.target,
            "persona": self.persona,
            "title": self.title[:TITLE_MAX],
            "body": self.body[:BODY_MAX],
            "channels": list(self.channels),
            "dedup_date": day.isoformat(),
        }


def _lead(config: Config, quests: list[Quest]) -> str | None:
    """The persona with most of today's quests, else the first in config order."""
    counts: dict[str, int] = {}
    for q in quests:
        counts[q.persona.root] = counts.get(q.persona.root, 0) + 1
    order = [p.root for p in config.persona_order]
    if counts:
        return max(counts, key=lambda p: (counts[p], -order.index(p) if p in order else -99))
    return order[0] if order else None


def _finished_on(q: Quest, day: date, tz) -> bool:
    return (
        q.status.value in FINISHED
        and q.completed_at is not None
        and q.completed_at.astimezone(tz).date() == day
    )


def streak_days(quests: list[Quest], now: datetime) -> int:
    """Consecutive days before today with a finished quest (today is what's at risk)."""
    days = {
        q.completed_at.astimezone(now.tzinfo).date()
        for q in quests
        if q.status.value in FINISHED and q.completed_at is not None
    }
    count, cursor = 0, now.date() - timedelta(days=1)
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def plan_notices(
    config: Config,
    quests: list[Quest],
    now: datetime,
    *,
    am_ready: bool,
    pm_done: bool,
) -> list[Notice]:
    """Everything due at `now` (local, aware). Safe to call every tick: the DB dedups."""
    today = now.date()
    todays = [
        q
        for q in quests
        if q.cadence.value == "daily" and q.scheduled_for is not None and q.scheduled_for <= today
    ]
    open_today = [q for q in todays if q.status.value in ACTIVE]
    lead = _lead(config, todays)
    notices: list[Notice] = []

    if am_ready and todays:
        minutes = sum(q.estimate_min for q in open_today)
        notices.append(
            Notice(
                "day_ready",
                "questboard://today",
                lead,
                "Today's quests are ready",
                f"{len(open_today)} quests, about {minutes} min.",
            )
        )
    if pm_done:
        done = sum(1 for q in quests if _finished_on(q, today, now.tzinfo))
        notices.append(
            Notice(
                "day_recap",
                "questboard://today",
                lead,
                "Day recap",
                f"{done} finished today; {len(open_today)} carried to tomorrow.",
            )
        )
    for q in quests:
        if q.status.value not in ACTIVE or q.deadline is None:
            continue
        target = f"questboard://quest/{q.id}"
        if q.deadline <= now:
            notices.append(Notice("quest_overdue", target, q.persona.root, "Overdue", q.title))
        elif q.deadline - now <= DUE_SOON:
            notices.append(Notice("quest_due", target, q.persona.root, "Due soon", q.title))
    if (
        now.time() >= STREAK_CHECK
        and not any(_finished_on(q, today, now.tzinfo) for q in quests)
        and (days := streak_days(quests, now)) > 0
    ):
        notices.append(
            Notice(
                "streak_risk",
                "questboard://today",
                lead,
                "Streak at risk",
                f"Finish one quest today to keep your {days}-day streak.",
            )
        )
    return notices


def in_quiet_hours(config: Config, now: datetime) -> bool:
    start = time.fromisoformat(config.quiet_hours.start.root)
    end = time.fromisoformat(config.quiet_hours.end.root)
    t = now.time()
    return start <= t < end if start <= end else t >= start or t < end


def deliverable(config: Config, now: datetime) -> bool:
    """Pending notifications go out only outside quiet hours; they wait, they aren't dropped."""
    return not in_quiet_hours(config, now)
