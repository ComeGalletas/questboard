# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from . import common_schema


class Status(StrEnum):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    partial = "partial"
    snoozed = "snoozed"
    deferred = "deferred"
    skipped = "skipped"
    forgotten = "forgotten"
    overdue = "overdue"
    abandoned = "abandoned"


class Source(StrEnum):
    manual = "manual"
    llm = "llm"
    llm_proposed = "llm-proposed"
    extractor = "extractor"
    calendar = "calendar"
    voice = "voice"


class Quest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID
    title: str = Field(..., max_length=120, min_length=1)
    notes: str | None = Field(None, max_length=2000)
    persona: common_schema.PersonaSlug
    cadence: common_schema.Cadence
    category: common_schema.Category
    status: Status
    estimate_min: int = Field(..., ge=1, le=1440)
    actual_min: int | None = Field(None, ge=0)
    scheduled_for: date | None = Field(
        None,
        description="Board day (daily), week start (weekly) or month start (monthly).",
    )
    deadline: AwareDatetime | None = None
    hard_deadline: bool = Field(
        ...,
        description="Hard-deadline obligations always carry over, ignoring carry caps.",
    )
    priority: int = Field(..., description="1 = highest.", ge=1, le=3)
    xp: int = Field(..., ge=0)
    carries: int = Field(..., ge=0)
    source: Source
    reference_token: common_schema.Token | None = Field(
        None, description="Links an extractor-created quest to its completion signal."
    )
    parent_id: UUID | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime
