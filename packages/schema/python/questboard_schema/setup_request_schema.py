# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    user = "user"
    assistant = "assistant"


class Message(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    role: Role
    content: str = Field(..., max_length=2000, min_length=1)


class SetupRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    messages: list[Message] = Field(..., max_length=40, min_length=1)
