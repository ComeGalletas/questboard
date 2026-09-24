# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from . import common_schema


class ProviderHealth(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    reachable: bool
    checked_at: AwareDatetime


class RunnerState(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    user_id: UUID
    heartbeat_at: AwareDatetime | None
    last_am_success: AwareDatetime | None
    last_pm_success: AwareDatetime | None
    lock_holder: str | None = None
    lock_acquired_at: AwareDatetime | None = None
    provider_health: dict[common_schema.ProviderName, ProviderHealth] = Field(
        ..., description="Last reachability check per provider."
    )
    runner_version: str | None = None
    updated_at: AwareDatetime | None = None
