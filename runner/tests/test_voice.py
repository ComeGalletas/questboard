"""Voice grammar and quest matching, locked to the fixtures the web parser also uses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner.voice.grammar import parse_command
from runner.voice.match import match_quest

FIXTURES = json.loads(
    (Path(__file__).resolve().parents[2] / "packages/schema/fixtures/voice.json").read_text()
)


@pytest.mark.parametrize("case", FIXTURES["parse"], ids=lambda c: c["text"] or "<empty>")
def test_parse_matches_shared_fixtures(case: dict) -> None:
    got = parse_command(case["text"], FIXTURES["today"], case.get("hint", "en"))
    assert got.model_dump(mode="json", exclude_none=True) == case["expect"]


@pytest.mark.parametrize("case", FIXTURES["match"]["cases"], ids=lambda c: c["ref"])
def test_match_matches_shared_fixtures(case: dict) -> None:
    quests = [(q["id"], q["title"]) for q in FIXTURES["match"]["quests"]]
    assert match_quest(case["ref"], quests).as_dict() == case["expect"]
