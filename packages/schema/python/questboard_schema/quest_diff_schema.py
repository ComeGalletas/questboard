# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class QuestDraft(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    title: str = Field(..., max_length=120, min_length=1)
    notes: str | None = Field(None, max_length=2000)
    persona: common_schema.PersonaSlug
    cadence: common_schema.Cadence
    category: common_schema.Category
    estimate_min: int = Field(..., ge=1, le=1440)
    scheduled_for: date | None = None
    deadline: AwareDatetime | None = None
    priority: int = Field(..., ge=1, le=3)
    parent_id: UUID | None = None


class QuestChanges(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    title: str | None = Field(None, max_length=120, min_length=1)
    notes: str | None = Field(None, max_length=2000)
    persona: common_schema.PersonaSlug | None = None
    estimate_min: int | None = Field(None, ge=1, le=1440)
    scheduled_for: date | None = None
    deadline: AwareDatetime | None = None
    priority: int | None = Field(None, ge=1, le=3)


class AddOp(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    op: Literal["add"]
    quest: QuestDraft
    reason: str = Field(..., max_length=300, min_length=1)


class UpdateOp(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    op: Literal["update"]
    quest_id: UUID
    changes: QuestChanges
    reason: str = Field(..., max_length=300, min_length=1)


class DropOp(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    op: Literal["drop"]
    quest_id: UUID
    reason: str = Field(..., max_length=300, min_length=1)


class QuestOp(RootModel[AddOp | UpdateOp | DropOp]):
    root: AddOp | UpdateOp | DropOp = Field(..., discriminator="op")


class QuestDiff(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    ops: list[QuestOp] = Field(..., max_length=50)
    summary: str | None = Field(None, max_length=500)
