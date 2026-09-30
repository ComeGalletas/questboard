"""Weekly / monthly retro: asked once per period, model or fixed questions, answers reach plans."""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.llm_run_schema import Status, Trigger

from runner.engine.period import period_job
from runner.engine.retro import FALLBACK, reflection, reviewed_period
from runner.repo import MemoryRepo
from runner.scheduler.core import Scheduler

sys.path.insert(0, str(Path(__file__).parent))
from test_engine import CONFIG, PACKS, ScriptedProvider, quest  # noqa: E402

SUNDAY = datetime(2026, 9, 27, 18, 0, tzinfo=ZoneInfo("America/Bogota"))
QUESTIONS = {
    "questions": [
        "The gym sessions slipped twice; what got in the way?",
        "Reading went well. What made it easy?",
    ]
}
POOL_FAILS = {"lines": []}  # the milestone pool after the plan; invalid is fine here


def weekly(repo: MemoryRepo, provider: ScriptedProvider) -> Scheduler:
    return Scheduler(
        repo=repo,
        handlers={JobName.weekly: lambda c: period_job("weekly", c, PACKS)},
        providers={ProviderName.claude_cli: provider},
        clock=lambda: SUNDAY.astimezone(UTC),
    )


def last_week() -> list:
    return [
        quest(title="Gym", status="done", scheduled_for=date(2026, 9, 22), cadence="daily"),
        quest(title="Read", status="skipped", scheduled_for=date(2026, 9, 25), cadence="daily"),
    ]


def test_reviewed_period() -> None:
    assert reviewed_period("weekly", date(2026, 9, 28)) == (date(2026, 9, 21), date(2026, 9, 27))
    assert reviewed_period("monthly", date(2026, 10, 1)) == (date(2026, 9, 1), date(2026, 9, 30))


def test_the_weekly_job_asks_about_the_week_that_ended_once() -> None:
    repo = MemoryRepo(CONFIG)
    repo.quests = last_week()
    provider = ScriptedProvider(QUESTIONS, {"ops": []}, POOL_FAILS, POOL_FAILS)
    [d] = weekly(repo, provider).evaluate(Trigger.tick)
    assert d.status == Status.succeeded, d.reason

    [retro] = repo.retros
    assert (retro["period_start"], retro["period_end"]) == ("2026-09-21", "2026-09-27")
    assert retro["source"] == "model" and retro["status"] == "open"
    assert [q["id"] for q in retro["questions"]] == ["q1", "q2"]
    assert "slipped twice" in retro["questions"][0]["text"]
    prompt = json.loads(provider.requests[0].prompt)
    assert {q["title"] for q in prompt["quests"]} == {"Gym", "Read"}

    # A forced re-run of the same week doesn't ask again.
    provider = ScriptedProvider({"ops": []}, POOL_FAILS, POOL_FAILS)
    [d] = weekly(repo, provider).evaluate(Trigger.manual, force=True)
    assert d.status == Status.succeeded, d.reason
    assert len(repo.retros) == 1


def test_fixed_questions_when_no_model_answers_and_none_when_nothing_happened() -> None:
    repo = MemoryRepo(CONFIG)
    repo.quests = last_week()
    bad = {"questions": ["Call me at 300 555 1234 ok?", "x" * 20]}
    provider = ScriptedProvider(bad, bad, {"ops": []}, POOL_FAILS, POOL_FAILS)
    [d] = weekly(repo, provider).evaluate(Trigger.tick)
    assert d.status == Status.succeeded, d.reason
    [retro] = repo.retros
    assert retro["source"] == "fallback"
    assert [q["text"] for q in retro["questions"]] == FALLBACK["weekly"]

    empty = MemoryRepo(CONFIG)
    [d] = weekly(empty, ScriptedProvider({"ops": []}, POOL_FAILS, POOL_FAILS)).evaluate(
        Trigger.tick
    )
    assert d.status == Status.succeeded and empty.retros == []


def test_answers_reach_the_next_plan() -> None:
    repo = MemoryRepo(CONFIG)
    repo.retros = [
        {
            "id": "r1",
            "cadence": "weekly",
            "period_start": "2026-09-14",
            "period_end": "2026-09-20",
            "questions": [{"id": "q1", "text": "What got in the way?"}, {"id": "q2", "text": "?"}],
            "answers": [
                {"id": "q1", "answer": "Late meetings on Tuesdays"},
                {"id": "q2", "answer": " "},
            ],
            "status": "answered",
            "source": "model",
        }
    ]
    provider = ScriptedProvider({"ops": []}, POOL_FAILS, POOL_FAILS)
    [d] = weekly(repo, provider).evaluate(Trigger.tick)
    assert d.status == Status.succeeded, d.reason
    plan_prompt = provider.requests[0].prompt
    assert "Late meetings on Tuesdays" in plan_prompt
    assert "reflection" in provider.requests[0].system


def test_reflection_keeps_only_answered_questions() -> None:
    retro = {
        "cadence": "monthly",
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "questions": [{"id": "q1", "text": "A?"}, {"id": "q2", "text": "B?"}],
        "answers": [{"id": "q2", "answer": "Because."}],
        "status": "answered",
    }
    assert reflection(retro) == {
        "cadence": "monthly",
        "period": ["2026-09-01", "2026-09-30"],
        "answers": [{"question": "B?", "answer": "Because."}],
    }
    assert reflection({**retro, "status": "skipped"}) is None
    assert reflection(None) is None
