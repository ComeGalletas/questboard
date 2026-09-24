# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema, config_schema


class Capacity(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    weekday_hours: float = Field(..., ge=0.0, le=24.0)
    weekend_hours: float = Field(..., ge=0.0, le=24.0)
    focus_factor: float = Field(..., gt=0.0, le=1.0)


class ConfigPatch(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    timezone: str | None = Field(None, max_length=64, min_length=1)
    goals: list[config_schema.Goal] | None = Field(None, max_length=12)
    capacity: Capacity | None = None
    quiet_hours: common_schema.QuietHours | None = None
    persona_order: list[common_schema.PersonaSlug] | None = Field(None, max_length=12)


class SetupTurn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    reply: str = Field(..., max_length=1500, min_length=1)
    config_patch: ConfigPatch | None
    done: bool = Field(
        ..., description="True when the assistant thinks setup is complete."
    )
