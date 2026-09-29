# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class Outcome(StrEnum):
    sent = "sent"
    removed = "removed"
    failed = "failed"


class Device(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    device: str = Field(..., max_length=80)
    outcome: Outcome = Field(
        ...,
        description="removed = the push service said the endpoint is gone, so its row was deleted.",
    )
    error: str | None = Field(None, max_length=120)


class NotifyTestResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    kind: common_schema.NotificationKind
    target: str = Field(..., pattern="^questboard://")
    devices: list[Device]
