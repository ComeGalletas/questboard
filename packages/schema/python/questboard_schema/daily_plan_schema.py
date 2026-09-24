# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema, fallback_lines_schema, quest_diff_schema


class Trigger(StrEnum):
    all_done = "all_done"
    half_by_noon = "half_by_noon"
    nothing_by_15 = "nothing_by_15"
    over_capacity = "over_capacity"


class Condition(StrEnum):
    any = "any"
    pleased = "pleased"
    neutral = "neutral"
    concerned = "concerned"


class BoardLine(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    persona: common_schema.PersonaSlug
    trigger: Trigger
    variant: int = Field(..., ge=1, le=3)
    condition: Condition
    text: str = Field(..., max_length=280, min_length=1)


class QuestLines(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    quest: str = Field(
        ...,
        description="An existing quest id, or new:N for the N-th add op (0-based) in diff.ops.",
        pattern="^([0-9a-f-]{36}|new:[0-9]{1,2})$",
    )
    persona: common_schema.PersonaSlug
    lines: list[fallback_lines_schema.FallbackLine] = Field(..., max_length=60)


class DailyPlan(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    diff: quest_diff_schema.QuestDiff
    quest_lines: list[QuestLines] = Field(..., max_length=40)
    board_lines: list[BoardLine] = Field(..., max_length=48)
