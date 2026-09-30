# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from . import common_schema


class Channel(StrEnum):
    pc = "pc"
    push = "push"


class Notification(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID
    kind: common_schema.NotificationKind
    target: str = Field(
        ..., description="Deep link the notification opens.", pattern="^questboard://"
    )
    persona: str | None = Field(None, pattern="^[a-z][a-z0-9_-]{1,31}$")
    dedup_date: date
    channels: list[Channel]
    title: str | None = Field(None, max_length=80)
    body: str | None = Field(None, max_length=280)
    sent_at: AwareDatetime | None = Field(
        None, description="Released for delivery (after quiet hours). Null while held."
    )
    pc_shown_at: AwareDatetime | None = Field(
        None,
        description="When the desktop shell showed it; each notification shows on the PC once.",
    )
    created_at: AwareDatetime
