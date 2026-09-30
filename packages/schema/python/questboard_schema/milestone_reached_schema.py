# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from . import common_schema


class MilestoneReached(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    key: str = Field(..., max_length=120, pattern="^[a-z0-9_:.-]+$")
    milestone: common_schema.MilestoneId
    label: str = Field(
        ...,
        description='What fills {milestone}, e.g. "7-day streak".',
        max_length=80,
        min_length=1,
    )
    reached_at: AwareDatetime
