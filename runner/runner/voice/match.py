"""Which open quest a spoken name means. Mirrors apps/web/src/voice/match.ts; both are locked to
packages/schema/fixtures/voice.json."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from runner.voice.grammar import normalize

STOPWORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "my",
        "to",
        "of",
        "and",
        "for",
        "task",
        "quest",
        "el",
        "la",
        "los",
        "las",
        "lo",
        "un",
        "una",
        "mi",
        "mis",
        "de",
        "del",
        "al",
        "y",
        "tarea",
        "mision",
    ]
)
MIN_SCORE = 0.5


@dataclass(frozen=True)
class QuestMatch:
    kind: Literal["match", "ambiguous", "none"]
    ids: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        if self.kind == "match":
            return {"kind": "match", "id": self.ids[0]}
        if self.kind == "ambiguous":
            return {"kind": "ambiguous", "ids": list(self.ids)}
        return {"kind": "none"}


def _words(s: str) -> list[str]:
    return [w for w in re.split(r"[^a-z0-9ñ]+", normalize(s)) if w and w not in STOPWORDS]


def _same(a: str, b: str) -> bool:
    """Same word, or one a prefix of the other (impuesto / impuestos) once both have 4+ letters."""
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


def match_quest(ref: str, quests: Iterable[tuple[str, str]]) -> QuestMatch:
    """quests: (id, title) pairs. Score = share of the spoken words found in the title; the best
    unique score >= 0.5 wins."""
    said = _words(ref)
    if not said:
        return QuestMatch("none")
    best = 0.0
    ids: list[str] = []
    for quest_id, title in quests:
        words = _words(title)
        hits = sum(1 for w in said if any(_same(w, t) for t in words))
        score = hits / len(said)
        if score < MIN_SCORE:
            continue
        if score > best:
            best, ids = score, [quest_id]
        elif score == best:
            ids.append(quest_id)
    if not ids:
        return QuestMatch("none")
    return QuestMatch("match" if len(ids) == 1 else "ambiguous", tuple(ids))
