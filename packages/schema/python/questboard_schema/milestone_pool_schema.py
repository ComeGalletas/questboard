# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class Line(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    persona: common_schema.PersonaSlug
    milestone: common_schema.MilestoneId
    variant: int = Field(..., ge=1, le=2)
    text: str = Field(
        ...,
        description='May use {milestone} (e.g. "7-day streak") and {streak}.',
        max_length=200,
        min_length=1,
    )


class MilestonePool(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    lines: list[Line] = Field(..., max_length=64)
