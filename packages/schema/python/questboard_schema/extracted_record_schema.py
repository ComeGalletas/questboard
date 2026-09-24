# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class Kind(StrEnum):
    obligation = "obligation"
    completion = "completion"


class Instruction(RootModel[str]):
    root: str = Field(..., max_length=200)


class Money(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    value: float = Field(..., ge=0.0)
    currency: str = Field(..., pattern="^[A-Z]{3}$")


class ExtractedRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    category: common_schema.Category
    kind: Kind = Field(
        ...,
        description="`completion` = receipt / delivered / confirmed signal that auto-resolves by reference_token.",
    )
    entity_token: common_schema.Token
    amount: Money | None = None
    due_at: AwareDatetime | None = None
    event_at: AwareDatetime | None = None
    location: str | None = Field(
        None, description="Sanitized location text or token.", max_length=200
    )
    instructions: list[Instruction] = Field(..., max_length=10)
    reference_token: common_schema.Token | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
