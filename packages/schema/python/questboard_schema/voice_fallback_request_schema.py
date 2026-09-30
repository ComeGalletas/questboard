# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Lang(StrEnum):
    en = "en"
    es = "es"


class VoiceFallbackRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    utterance: str = Field(..., max_length=300, min_length=1)
    lang: Lang
    today: date = Field(
        ...,
        description="The user's local date, so relative days (\"next Saturday\") resolve like the grammar's.",
    )
