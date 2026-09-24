# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from datetime import date as date_aliased
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Intent(StrEnum):
    create = "create"
    complete = "complete"
    snooze = "snooze"
    defer = "defer"
    whats_next = "whats_next"
    confirm = "confirm"
    cancel = "cancel"
    unknown = "unknown"


class Lang(StrEnum):
    en = "en"
    es = "es"


class VoiceCommand(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    intent: Intent
    lang: Lang
    title: str | None = Field(
        None, description="create: the new quest's title.", max_length=120, min_length=1
    )
    quest: str | None = Field(
        None,
        description="complete / snooze / defer: how the user named the quest (matched in code).",
        max_length=120,
        min_length=1,
    )
    date: date_aliased | None = Field(
        None, description="create: the day to schedule; defer: the new day."
    )
    time: str | None = Field(
        None,
        description="create: local time of day, when one was said.",
        pattern="^([01][0-9]|2[0-3]):[0-5][0-9]$",
    )
    minutes: int | None = Field(
        None, description="snooze: how long, when one was said.", ge=1, le=1440
    )
