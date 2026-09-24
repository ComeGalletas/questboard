# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Trigger(StrEnum):
    assigned = "assigned"
    reminder_am = "reminder_am"
    reminder_mid = "reminder_mid"
    reminder_pm = "reminder_pm"
    started = "started"
    completed_early = "completed_early"
    completed_on_time = "completed_on_time"
    completed_late = "completed_late"
    partial = "partial"
    snoozed = "snoozed"
    deferred = "deferred"
    skipped = "skipped"
    forgotten = "forgotten"
    overdue_1d = "overdue_1d"
    overdue_3d = "overdue_3d"
    overdue_7d = "overdue_7d"
    carried_over = "carried_over"
    abandoned = "abandoned"
    all_done = "all_done"
    half_by_noon = "half_by_noon"
    nothing_by_15 = "nothing_by_15"
    over_capacity = "over_capacity"


class Condition(StrEnum):
    any = "any"
    pleased = "pleased"
    neutral = "neutral"
    concerned = "concerned"


class FallbackLine(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    trigger: Trigger
    variant: int = Field(..., ge=1, le=3)
    condition: Condition = Field(
        ...,
        description="Mood bucket; mood itself is computed in code from completion rate.",
    )
    text: str = Field(
        ...,
        description="May contain runtime placeholders {time_left} {streak} {days_carried} {actual_vs_estimate} {next_quest}.",
        max_length=280,
        min_length=1,
    )


class FallbackLines(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    lines: list[FallbackLine] = Field(..., min_length=1)
