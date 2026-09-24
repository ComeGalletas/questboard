# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel


class Common(RootModel[Any]):
    root: Any = Field(
        ...,
        description="Shared enums and value types referenced by the other schemas.",
        title="Common",
    )


class PersonaSlug(RootModel[str]):
    root: str = Field(
        ...,
        description="Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).",
        pattern="^[a-z][a-z0-9_-]{1,31}$",
    )


class Token(RootModel[str]):
    root: str = Field(
        ...,
        description="Pseudonym token issued by the local vault, e.g. PERSON_7, ORG_3, AMOUNT_2.",
        pattern="^[A-Z]+_[0-9]+$",
    )


class AmountToken(RootModel[str]):
    root: str = Field(
        ...,
        description="Pseudonym for a money amount. Value and currency stay in the local vault.",
        pattern="^AMOUNT_[0-9]+$",
    )


class Cadence(StrEnum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class Category(StrEnum):
    general = "general"
    ics = "ics"
    utilities = "utilities"
    government = "government"
    health = "health"
    delivery = "delivery"
    subscription = "subscription"
    jobs = "jobs"
    learning = "learning"
    personal = "personal"
    travel = "travel"


class ProviderName(StrEnum):
    claude_cli = "claude-cli"
    ollama = "ollama"
    claude_api = "claude-api"


class JobName(StrEnum):
    ingest = "ingest"
    daily_am = "daily_am"
    daily_pm = "daily_pm"
    weekly = "weekly"
    monthly = "monthly"
    persona_digest = "persona_digest"


class LocalTime(RootModel[str]):
    root: str = Field(
        ...,
        description="Wall-clock time HH:MM in the configured timezone.",
        pattern="^([01][0-9]|2[0-3]):[0-5][0-9]$",
    )


class QuietHours(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    start: LocalTime
    end: LocalTime
