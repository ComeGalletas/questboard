# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, RootModel


class DoItem(RootModel[str]):
    root: str = Field(..., max_length=120, min_length=1)


class DontItem(RootModel[str]):
    root: str = Field(..., max_length=120, min_length=1)


class SampleLine(RootModel[str]):
    root: str = Field(..., max_length=200, min_length=1)


class PersonaDigest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    voice: str = Field(
        ...,
        description="How the persona talks: tone, rhythm, recurring images.",
        max_length=400,
        min_length=1,
    )
    do: list[DoItem] = Field(..., max_length=6)
    dont: list[DontItem] = Field(..., max_length=6)
    sample_lines: list[SampleLine] = Field(
        ..., description="A few lines in character, to anchor the voice.", max_length=4
    )
