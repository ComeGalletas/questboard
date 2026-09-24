from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from questboard_schema.setup_turn_schema import SetupTurn

from runner.engine.setup import check_turn, merged_config
from runner.live import process_live
from runner.repo import MemoryRepo

sys.path.insert(0, str(Path(__file__).parent))
from test_engine import CONFIG, PACKS, ScriptedProvider  # noqa: E402

NOW = datetime(2026, 9, 25, 15, 0, tzinfo=UTC)
PERSONAS = {p.slug for p in PACKS}


def turn(**patch) -> SetupTurn:
    return SetupTurn.model_validate(
        {"reply": "Got it.", "config_patch": patch or None, "done": False}
    )


def test_patch_replaces_whole_keys_and_leaves_the_rest() -> None:
    t = turn(
        goals=[{"id": "g1", "title": "Learn Portuguese", "horizon": "year", "persona": "teacher"}],
        capacity={"weekday_hours": 2.5, "weekend_hours": 4, "focus_factor": 0.7},
    )
    assert check_turn(t, CONFIG, PERSONAS) == []
    merged = merged_config(CONFIG, t)
    assert [g.title for g in merged.goals] == ["Learn Portuguese"]
    assert merged.capacity.weekday_hours == 2.5
    assert merged.llm == CONFIG.llm  # out of the assistant's reach


def test_patch_rules() -> None:
    bad = turn(
        timezone="Mars/Olympus",
        persona_order=["coach", "wizard"],
        goals=[
            {"id": "g", "title": "A", "horizon": "week"},
            {"id": "g", "title": "B", "horizon": "week", "persona": "wizard"},
        ],
    )
    problems = "\n".join(check_turn(bad, CONFIG, PERSONAS))
    assert "IANA" in problems
    assert "persona_order: unknown" in problems
    assert "ids must be unique" in problems
    assert "goals: unknown persona" in problems


def request(**over):
    return {
        "id": over.pop("id", "r1"),
        "kind": "setup_assistant",
        "status": "pending",
        "created_at": NOW - timedelta(seconds=10),
        "payload": {"messages": [{"role": "user", "content": "I want to run a 10k"}]},
        **over,
    }


def test_setup_request_is_answered_with_a_validated_turn() -> None:
    repo = MemoryRepo(CONFIG)
    repo.requests = [request()]
    bad = {"reply": "Hi", "config_patch": {"timezone": "Nowhere/City"}, "done": False}
    good = {
        "reply": "How many hours do you have on weekdays?",
        "config_patch": {
            "goals": [{"id": "10k", "title": "Run a 10k", "horizon": "quarter", "persona": "coach"}]
        },
        "done": False,
    }
    provider = ScriptedProvider(bad, good)
    assert process_live(repo, CONFIG, [provider], NOW, PACKS) == 1
    req = repo.requests[0]
    assert req["status"] == "done"
    assert req["result"]["config_patch"]["goals"][0]["title"] == "Run a 10k"
    assert "IANA" in provider.requests[1].prompt  # retried with the problem
    assert "I want to run a 10k" in provider.requests[0].prompt
    assert repo.config == CONFIG  # nothing applied: the user decides


def test_queue_rules() -> None:
    class Down(ScriptedProvider):
        def is_available(self) -> bool:
            return False

    repo = MemoryRepo(CONFIG)
    repo.requests = [
        request(id="old", created_at=NOW - timedelta(days=2)),
        request(id="voice", kind="voice_fallback"),
        request(id="wait"),
    ]
    assert process_live(repo, CONFIG, [Down()], NOW, PACKS) == 0
    status = {r["id"]: r["status"] for r in repo.requests}
    assert status == {"old": "cancelled", "voice": "failed", "wait": "pending"}
