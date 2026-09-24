# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from datetime import date as date_aliased
from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from . import common_schema


class Slot(StrEnum):
    AM = "AM"
    PM = "PM"


class Trigger(StrEnum):
    tick = "tick"
    start = "start"
    network_up = "network_up"
    manual = "manual"


class Status(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    invalid_output = "invalid_output"
    skipped = "skipped"


class TokenUsage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    input: int = Field(..., ge=0)
    output: int = Field(..., ge=0)


class LLMRun(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID | None = None
    job: common_schema.JobName
    slot: Slot | None = Field(None, description="Only daily jobs have a slot.")
    date: date_aliased
    trigger: Trigger
    provider_used: common_schema.ProviderName | None = None
    attempt: int = Field(..., ge=1, le=3)
    status: Status
    tokens: TokenUsage | None = None
    error: str | None = Field(None, max_length=500)
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
