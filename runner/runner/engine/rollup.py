"""Parent/sub-quest roll-up (code, P2): how far an open weekly/monthly quest has come through its
sub-quests. The web app computes the same numbers in `apps/web/src/game/rollup.ts`.

A parent tracks the whole period's work: its estimate_min is the target, and every finished
sub-quest adds its actual minutes (its estimate when no time was logged). The parent is never
closed by code; the user turns it in.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from questboard_schema.quest_schema import Quest

from runner.repo import ACTIVE

FINISHED = ("done", "partial")


def period_end(q: Quest) -> date | None:
    """Last day of the period a weekly/monthly quest belongs to (inclusive)."""
    start = q.scheduled_for
    if start is None:
        return None
    if q.cadence.value == "weekly":
        return start + timedelta(days=6)
    if q.cadence.value == "monthly":
        return start.replace(day=calendar.monthrange(start.year, start.month)[1])
    return start


@dataclass(frozen=True)
class Rollup:
    done: int  # finished sub-quests
    open: int  # active sub-quests
    done_min: int
    planned_min: int  # estimates of the active sub-quests
    target_min: int

    @property
    def remaining_min(self) -> int:
        return max(0, self.target_min - self.done_min)

    @property
    def unplanned_min(self) -> int:
        """Work left that no open sub-quest carries yet."""
        return max(0, self.remaining_min - self.planned_min)


def _spent(q: Quest) -> int:
    return q.actual_min if q.actual_min is not None else q.estimate_min


def sub_quests(parent: Quest, quests: list[Quest]) -> list[Quest]:
    pid = str(parent.id)
    return [q for q in quests if q.parent_id is not None and str(q.parent_id) == pid]


def rollup(parent: Quest, quests: list[Quest]) -> Rollup:
    subs = sub_quests(parent, quests)
    finished = [q for q in subs if q.status.value in FINISHED]
    active = [q for q in subs if q.status.value in ACTIVE]
    return Rollup(
        done=len(finished),
        open=len(active),
        done_min=sum(_spent(q) for q in finished),
        planned_min=sum(q.estimate_min for q in active),
        target_min=parent.estimate_min,
    )
