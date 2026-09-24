# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class PersonaPack(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    name: str = Field(..., max_length=40, min_length=1)
    slug: common_schema.PersonaSlug
    accent: str = Field(..., pattern="^#[0-9a-f]{6}$")
    intensity: int = Field(
        ...,
        description="Escalation style, 0 = gentle, 3 = drill sergeant. Capped by code.",
        ge=0,
        le=3,
    )
    quiet_hours: common_schema.QuietHours | None = Field(
        None,
        description="Extra quiet hours for this persona; config quiet hours always apply too.",
    )
    owns: list[common_schema.Category] = Field(
        ..., description="Categories this persona hands out by default."
    )
    priority: int = Field(
        ...,
        description="Tie-break when several personas own a category; higher wins.",
        ge=0,
        le=100,
    )
