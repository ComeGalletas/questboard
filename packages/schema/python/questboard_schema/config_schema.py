# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class Capacity(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    weekday_hours: float = Field(..., ge=0.0, le=24.0)
    weekend_hours: float = Field(..., ge=0.0, le=24.0)
    focus_factor: float = Field(..., gt=0.0, le=1.0)


class XpWeights(RootModel[float]):
    root: float = Field(..., ge=0.0)


class PerJob(RootModel[list[common_schema.ProviderName]]):
    root: list[common_schema.ProviderName] = Field(..., min_length=1)


class Llm(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    providers: list[common_schema.ProviderName] = Field(..., min_length=1)
    per_job: dict[common_schema.JobName, PerJob] | None = Field(
        None, description="Per-job provider order override, keyed by job name."
    )


class Integrations(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    gmail: bool
    gcal: bool


class Features(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    three_d: bool
    mobile_rehydration: bool


class Notifications(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    persona_speech_per_day: int = Field(..., ge=0, le=10)
    persona_speech_on_mobile: bool


class Horizon(StrEnum):
    week = "week"
    month = "month"
    quarter = "quarter"
    year = "year"


class Goal(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: str = Field(..., min_length=1)
    title: str = Field(..., max_length=120, min_length=1)
    horizon: Horizon
    persona: common_schema.PersonaSlug | None = None


class QuietHours(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    start: common_schema.LocalTime
    end: common_schema.LocalTime


class Config(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    timezone: str = Field(
        ..., description="IANA zone, e.g. America/Bogota.", min_length=1
    )
    goals: list[Goal]
    capacity: Capacity
    quiet_hours: QuietHours
    xp_weights: dict[str, XpWeights] = Field(
        ..., description="Multiplier per category."
    )
    llm: Llm
    persona_order: list[common_schema.PersonaSlug]
    integrations: Integrations
    features: Features
    notifications: Notifications
