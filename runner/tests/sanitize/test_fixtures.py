"""Release gate (CLAUDE.md): adversarial emails must come out with no personal data.

Each fixture lists `secrets` (must not survive in any form: as text, case-insensitively, or as
the same digits inside any number left in the output), `keep` (content the extractors need),
`kinds` (tokens expected) and `drop` (credentials -> the message is dropped).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from runner.sanitize import MemoryVault, sanitize
from runner.sanitize.text import CAP

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("*.json"))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digits(s: str) -> str:
    return re.sub(r"\D", "", s)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_fixture(path: Path) -> None:
    f = load(path)
    vault = MemoryVault()
    out = sanitize(f["body"], vault, html=f["html"])
    text = out.text
    folded = text.casefold()
    numbers = [digits(n) for n in re.findall(r"\d[\d .,/-]*\d|\d", text)]
    for secret in f["secrets"]:
        assert secret.casefold() not in folded, f"{f['name']}: a secret survived"
        d = digits(secret)
        if len(d) >= 5:
            assert not any(d in n for n in numbers), f"{f['name']}: secret digits survived"
    for keep in f["keep"]:
        assert keep in text, f"{f['name']}: lost {keep!r}"
    for kind in f["kinds"]:
        assert re.search(rf"\b{kind}_\d+\b", text), f"{f['name']}: no {kind} token"
    assert out.drop == f["drop"]
    assert len(text) <= CAP + 2


def test_every_fixture_is_well_formed() -> None:
    assert len(FIXTURES) >= 20
    for path in FIXTURES:
        f = load(path)
        assert f["name"] == path.stem
        assert set(f) >= {"description", "body", "secrets", "keep", "kinds", "drop", "html"}
