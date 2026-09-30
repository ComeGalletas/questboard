"""Voice fallback (P1): sanitize -> model -> VoiceCommand, restored; transcripts never kept."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from runner.engine.voice_fallback import check_command, restore
from runner.live import VOICE_TTL, process_live
from runner.repo import MemoryRepo
from runner.sanitize.vault import MemoryVault

sys.path.insert(0, str(Path(__file__).parent))
from test_engine import CONFIG, PACKS, ScriptedProvider  # noqa: E402

NOW = datetime(2026, 9, 30, 15, 0, tzinfo=UTC)
TODAY = date(2026, 9, 30)  # a Wednesday


def voice(utterance: str, **over):
    return {
        "id": over.pop("id", "v1"),
        "kind": "voice_fallback",
        "status": "pending",
        "created_at": over.pop("created_at", NOW - timedelta(seconds=5)),
        "payload": {"utterance": utterance, "lang": "es", "today": TODAY.isoformat()},
        **over,
    }


def test_private_details_reach_the_model_as_tokens_and_come_back_on_the_card() -> None:
    repo = MemoryRepo(CONFIG)
    repo.requests = [voice("tengo que llamar a María García el sábado por los 350.000 pesos")]
    provider = ScriptedProvider(
        {
            "intent": "create",
            "lang": "es",
            "title": "Llamar a PERSON_1 por AMOUNT_1",
            "date": "2026-10-03",
        }
    )
    assert process_live(repo, CONFIG, [provider], NOW, PACKS) == 1

    prompt = provider.requests[0].prompt
    assert "María" not in prompt and "350.000" not in prompt
    assert "PERSON_1" in prompt and "AMOUNT_1" in prompt
    assert '"today": "2026-09-30"' in prompt and "Wednesday" in prompt

    req = repo.requests[0]
    assert req["status"] == "done"
    assert req["result"] == {
        "intent": "create",
        "lang": "es",
        "title": "Llamar a María García por 350.000 pesos",
        "date": "2026-10-03",
    }
    assert req["payload"] == {}, "the transcript is blanked once answered"


def test_bad_answers_are_retried_with_the_problem() -> None:
    repo = MemoryRepo(CONFIG)
    repo.requests = [voice("apunta que ya terminé lo del gimnasio, me tomó una hora")]
    provider = ScriptedProvider(
        {"intent": "confirm", "lang": "es"},
        {"intent": "complete", "lang": "es", "quest": "gimnasio", "minutes": 60},
    )
    assert process_live(repo, CONFIG, [provider], NOW, PACKS) == 1
    assert "not allowed" in provider.requests[1].prompt
    assert repo.requests[0]["result"] == {
        "intent": "complete",
        "lang": "es",
        "quest": "gimnasio",
        "minutes": 60,
    }


def test_command_rules() -> None:
    from questboard_schema.voice_command_schema import VoiceCommand

    def problems(**cmd) -> list[str]:
        return check_command(VoiceCommand(lang="en", **cmd), TODAY, {"PERSON_1"})

    assert problems(intent="create", title="Call PERSON_1") == []
    assert problems(intent="create") == ["create needs a title"]
    assert problems(intent="snooze") == ["snooze needs quest"]
    assert "defer needs a date" in problems(intent="defer", quest="gym")
    assert problems(intent="create", title="x", date="2028-01-01") == [
        "date is outside the next year"
    ]
    assert "tokens that weren't in the request" in problems(intent="create", title="Pay ORG_4")[0]
    assert "contains" in problems(intent="create", title="Email ana@example.com")[0]


def test_restore_puts_words_back_and_leaves_unknown_tokens() -> None:
    from questboard_schema.voice_command_schema import VoiceCommand

    vault = MemoryVault()
    token = vault.token_for("PERSON", "Ana")
    cmd = restore(VoiceCommand(intent="create", lang="en", title=f"Call {token}"), vault)
    assert cmd.title == "Call Ana"


def test_passwords_and_codes_are_never_sent_to_a_model() -> None:
    repo = MemoryRepo(CONFIG)
    repo.requests = [voice("mi contraseña es Tigre2026! apúntala")]
    provider = ScriptedProvider()  # would fail if called
    assert process_live(repo, CONFIG, [provider], NOW, PACKS) == 1
    assert provider.requests == []
    assert repo.requests[0]["result"] == {"intent": "unknown", "lang": "es"}
    assert repo.requests[0]["payload"] == {}


def test_failures_blank_the_transcript_too() -> None:
    repo = MemoryRepo(CONFIG)
    repo.requests = [voice("algo que el modelo no sabe responder")]
    provider = ScriptedProvider({"intent": "confirm", "lang": "es"}, {"intent": "cancel"})
    assert process_live(repo, CONFIG, [provider], NOW, PACKS) == 0
    req = repo.requests[0]
    assert req["status"] == "failed"
    assert req["error"] == "no provider could interpret it"  # never model or user text
    assert req["payload"] == {}


def test_stale_voice_requests_are_deleted_other_kinds_kept() -> None:
    repo = MemoryRepo(CONFIG)
    old = NOW - VOICE_TTL - timedelta(seconds=1)
    repo.requests = [
        voice("viejo", id="stale", created_at=old, status="done", payload={}),
        voice("pendiente viejo", id="stale-pending", created_at=old),
        {
            "id": "setup",
            "kind": "setup_assistant",
            "status": "done",
            "created_at": old,
            "payload": {},
        },
    ]
    process_live(repo, CONFIG, [], NOW, PACKS)
    assert [r["id"] for r in repo.requests] == ["setup"]
