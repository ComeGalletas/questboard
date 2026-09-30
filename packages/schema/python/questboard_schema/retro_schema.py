# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Cadence(StrEnum):
    weekly = "weekly"
    monthly = "monthly"


class Status(StrEnum):
    open = "open"
    answered = "answered"
    skipped = "skipped"


class Source(StrEnum):
    model = "model"
    fallback = "fallback"


class RetroQuestion(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: str = Field(..., pattern="^q[1-3]$")
    text: str = Field(..., max_length=160, min_length=1)


class RetroAnswer(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: str = Field(..., pattern="^q[1-3]$")
    answer: str = Field(..., max_length=500)


class Retro(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID
    cadence: Cadence
    period_start: date = Field(..., description="First day of the period reviewed.")
    period_end: date
    questions: list[RetroQuestion] = Field(..., max_length=3, min_length=2)
    answers: list[RetroAnswer] | None = Field(None, max_length=3)
    status: Status
    source: Source
    answered_at: AwareDatetime | None = None
    created_at: AwareDatetime
