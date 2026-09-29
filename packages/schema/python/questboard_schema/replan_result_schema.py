# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Status(StrEnum):
    succeeded = "succeeded"
    skipped = "skipped"
    failed = "failed"
    invalid_output = "invalid_output"


class ReplanResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    status: Status
    reason: str = Field(..., max_length=200)
    ops_count: int | None = Field(None, ge=0)
