# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, RootModel


class Question(RootModel[str]):
    root: str = Field(..., max_length=160, min_length=8)


class RetroQuestions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    questions: list[Question] = Field(..., max_length=3, min_length=2)
