"""Effort calibration: how long quests really take vs their estimates, per category.

Median of actual_min / estimate_min over finished quests in the last 30 days, only for categories
with at least 3 samples, clamped to 0.5x-3x so one outlier week can't wreck plans. Fed to the
planning prompts so estimates converge on reality (and shown in the app when adding a quest).
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import median

from questboard_schema.quest_schema import Quest

WINDOW_DAYS = 30
MIN_SAMPLES = 3
CLAMP = (0.5, 3.0)


def calibration(quests: list[Quest], today: date) -> dict[str, dict[str, float | int]]:
    since = today - timedelta(days=WINDOW_DAYS)
    ratios: dict[str, list[float]] = {}
    for q in quests:
        if (
            q.status.value in ("done", "partial")
            and q.actual_min is not None
            and q.actual_min > 0
            and q.completed_at is not None
            and q.completed_at.date() >= since
        ):
            ratios.setdefault(q.category.value, []).append(q.actual_min / q.estimate_min)
    table = {}
    for category, values in sorted(ratios.items()):
        if len(values) >= MIN_SAMPLES:
            ratio = min(max(median(values), CLAMP[0]), CLAMP[1])
            table[category] = {"ratio": round(ratio, 2), "samples": len(values)}
    return table
