# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Job(StrEnum):
    daily_am = "daily_am"
    weekly = "weekly"
    monthly = "monthly"


class ReplanRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    job: Job
