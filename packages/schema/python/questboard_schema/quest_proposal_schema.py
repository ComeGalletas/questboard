# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from . import fallback_lines_schema, quest_diff_schema


class Op(StrEnum):
    add = "add"
    update = "update"
    drop = "drop"


class Status(StrEnum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    superseded = "superseded"


class QuestProposal(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID
    run_id: UUID | None = None
    op: Op
    quest_id: UUID | None = None
    payload: quest_diff_schema.QuestOp = Field(
        ..., description="The op exactly as proposed (validated)."
    )
    lines: list[fallback_lines_schema.FallbackLine] | None = Field(
        None,
        description="Dialogue for a proposed add; inserted into persona_lines when accepted.",
    )
    status: Status
    decided_at: AwareDatetime | None = None
    created_at: AwareDatetime
