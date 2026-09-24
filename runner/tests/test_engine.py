from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.config_schema import Config
from questboard_schema.daily_plan_schema import DailyPlan
from questboard_schema.llm_run_schema import Status, Trigger
from questboard_schema.quest_schema import Quest

from runner.engine.carry import carry_patch
from runner.engine.daily import build_context, capacity_minutes, daily_am, daily_pm
from runner.engine.packs import load_packs
from runner.engine.prompts import system_prompt
from runner.engine.validators import BOARD_TRIGGERS, QUEST_TRIGGERS, PlanContext, check_plan
from runner.providers.base import GenerationRequest, Provider, RawCompletion
from runner.repo import MemoryRepo
from runner.scheduler.core import Scheduler

BOGOTA = ZoneInfo("America/Bogota")
TODAY = date(2026, 9, 25)  # Friday
NOW = datetime(2026, 9, 25, 6, 0, tzinfo=BOGOTA)
CONFIG = Config.model_validate(
    {
        "timezone": "America/Bogota",
        "goals": [{"id": "g1", "title": "Run a 10k", "horizon": "quarter", "persona": "coach"}],
        "capacity": {"weekday_hours": 2, "weekend_hours": 5, "focus_factor": 0.5},
        "quiet_hours": {"start": "22:00", "end": "07:00"},
        "xp_weights": {},
        "llm": {"providers": ["claude-cli"]},
        "persona_order": ["coach", "teacher", "mom", "quartermaster"],
        "integrations": {"gmail": False, "gcal": False},
        "features": {"three_d": False, "mobile_rehydration": False},
        "notifications": {"persona_speech_per_day": 2, "persona_speech_on_mobile": False},
    }
)
PACKS = load_packs()


def quest(**over: Any) -> Quest:
    base = {
        "id": str(uuid.uuid4()),
        "title": "Stretch",
        "persona": "coach",
        "cadence": "daily",
        "category": "health",
        "status": "open",
        "estimate_min": 20,
        "priority": 2,
        "xp": 20,
        "carries": 0,
        "hard_deadline": False,
        "source": "manual",
        "scheduled_for": TODAY.isoformat(),
        "created_at": "2026-09-24T12:00:00Z",
        "updated_at": "2026-09-24T12:00:00Z",
    }
    return Quest.model_validate({**base, **over})


def lines(persona: str) -> list[dict[str, Any]]:
    return [
        {"trigger": t, "variant": v, "condition": "any", "text": f"{t} line {v}. {{streak}}"}
        for t in QUEST_TRIGGERS
        for v in (1, 2)
    ]


def board(persona: str = "coach") -> list[dict[str, Any]]:
    return [
        {"persona": persona, "trigger": t, "variant": v, "condition": "any", "text": f"{t}!"}
        for t in BOARD_TRIGGERS
        for v in (1, 2)
    ]


def plan(ops: list[dict[str, Any]], quest_lines: list[dict[str, Any]], **extra: Any) -> dict:
    return {"diff": {"ops": ops}, "quest_lines": quest_lines, "board_lines": board(), **extra}


def ctx_for(quests: list[Quest]) -> PlanContext:
    _, pc, _ = build_context(CONFIG, quests, [], TODAY)
    return PlanContext(**{**pc.__dict__, "personas": {p.slug for p in PACKS}})


ADD_RUN = {
    "op": "add",
    "reason": "Goal: run a 10k",
    "quest": {
        "title": "Easy 3 km run",
        "persona": "coach",
        "cadence": "daily",
        "category": "health",
        "estimate_min": 25,
        "priority": 2,
        "scheduled_for": TODAY.isoformat(),
    },
}


# -- carry-over ---------------------------------------------------------------------------


def test_carry_moves_unfinished_daily_quests_to_tomorrow_up_to_three_times() -> None:
    evening = datetime(2026, 9, 25, 21, 0, tzinfo=BOGOTA)
    assert carry_patch(quest(), TODAY, evening) == {
        "status": "open",
        "scheduled_for": "2026-09-26",
        "carries": 1,
        "snoozed_until": None,
    }
    assert carry_patch(quest(carries=3), TODAY, evening) == {
        "status": "abandoned",
        "snoozed_until": None,
    }
    hard = quest(carries=5, hard_deadline=True, deadline="2026-09-25T12:00:00Z")
    assert carry_patch(hard, TODAY, evening)["status"] == "overdue"
    assert carry_patch(hard, TODAY, evening)["carries"] == 6


def test_carry_ignores_done_future_and_non_daily() -> None:
    evening = datetime(2026, 9, 25, 21, 0, tzinfo=BOGOTA)
    done = quest(status="done", completed_at="2026-09-25T15:00:00Z")
    assert carry_patch(done, TODAY, evening) is None
    assert carry_patch(quest(scheduled_for="2026-09-27", status="deferred"), TODAY, evening) is None
    assert carry_patch(quest(cadence="weekly"), TODAY, evening) is None


# -- validators ---------------------------------------------------------------------------


def test_valid_plan_passes() -> None:
    q = quest()
    p = DailyPlan.model_validate(
        plan(
            [ADD_RUN],
            [
                {"quest": str(q.id), "persona": "coach", "lines": lines("coach")},
                {"quest": "new:0", "persona": "coach", "lines": lines("coach")},
            ],
        )
    )
    assert check_plan(p, ctx_for([q])) == []


@pytest.mark.parametrize(
    ("op", "problem"),
    [
        ({**ADD_RUN, "quest": {**ADD_RUN["quest"], "category": "utilities"}}, "extractors only"),
        (
            {**ADD_RUN, "quest": {**ADD_RUN["quest"], "deadline": "2026-09-30T12:00:00Z"}},
            "may not set a deadline",
        ),
        ({**ADD_RUN, "quest": {**ADD_RUN["quest"], "persona": "wizard"}}, "not an installed pack"),
        ({**ADD_RUN, "quest": {**ADD_RUN["quest"], "estimate_min": 200}}, "of capacity"),
        (
            {"op": "drop", "quest_id": str(uuid.uuid4()), "reason": "stale"},
            "not an open quest",
        ),
        ({**ADD_RUN, "quest": {**ADD_RUN["quest"], "title": "Call 300 555 1234"}}, "long number"),
    ],
)
def test_plan_rules(op: dict[str, Any], problem: str) -> None:
    q = quest()
    ql = [{"quest": str(q.id), "persona": "coach", "lines": lines("coach")}]
    if op["op"] == "add":
        ql.append({"quest": "new:0", "persona": "coach", "lines": lines("coach")})
    problems = check_plan(DailyPlan.model_validate(plan([op], ql)), ctx_for([q]))
    assert any(problem in p for p in problems), problems


def test_updates_may_not_touch_deadlines_and_lines_must_cover_the_board() -> None:
    q = quest()
    upd = {
        "op": "update",
        "quest_id": str(q.id),
        "reason": "x",
        "changes": {"deadline": "2026-09-30T12:00:00Z"},
    }
    bad_lines = [{"trigger": "assigned", "variant": 1, "condition": "any", "text": "Hi me@x.co"}]
    p = DailyPlan.model_validate(
        {
            "diff": {"ops": [upd]},
            "quest_lines": [
                {"quest": str(q.id), "persona": "mom", "lines": bad_lines},
                {"quest": "new:3", "persona": "coach", "lines": []},
            ],
            "board_lines": [],
        }
    )
    problems = "\n".join(check_plan(p, ctx_for([q])))
    assert "may not change deadlines" in problems
    assert "persona must be the quest's persona" in problems
    assert "missing triggers" in problems
    assert "email address" in problems
    assert "new:3 does not match an add op" in problems
    assert "board_lines: missing triggers" in problems
    assert "me@x.co" not in problems  # problems never quote values


# -- daily_am end to end --------------------------------------------------------------------


class ScriptedProvider(Provider):
    name = ProviderName.claude_cli

    def __init__(self, *outputs: dict[str, Any]):
        self.outputs = list(outputs)
        self.requests: list[GenerationRequest] = []

    def is_available(self) -> bool:
        return True

    def _complete(self, request: GenerationRequest, schema: dict[str, Any]) -> RawCompletion:
        self.requests.append(request)
        return RawCompletion(data=json.dumps(self.outputs.pop(0)))


def scheduler(repo: MemoryRepo, provider: Provider, at: datetime) -> Scheduler:
    return Scheduler(
        repo=repo,
        handlers={
            JobName.daily_am: lambda ctx: daily_am(ctx, PACKS),
            JobName.daily_pm: daily_pm,
        },
        providers={ProviderName.claude_cli: provider},
        clock=lambda: at.astimezone(UTC),
    )


def test_daily_am_caches_proposals_and_dialogue_without_touching_quests() -> None:
    q = quest()
    repo = MemoryRepo(CONFIG)
    repo.quests = [q]
    repo.proposals = [{"id": "old", "status": "pending", "op": "drop"}]
    repo.lines = [{"quest_id": str(q.id), "trigger": "assigned", "used_at": None, "text": "stale"}]
    good = plan(
        [ADD_RUN],
        [
            {"quest": str(q.id), "persona": "coach", "lines": lines("coach")},
            {"quest": "new:0", "persona": "coach", "lines": lines("coach")},
        ],
    )
    bad = {**good, "board_lines": []}  # fails the board-coverage rule -> retried once
    provider = ScriptedProvider(bad, good)
    [d] = scheduler(repo, provider, NOW).evaluate(Trigger.tick, only=JobName.daily_am)

    assert d.status == Status.succeeded
    assert "board_lines: missing triggers" in provider.requests[1].prompt
    assert repo.quests == [q]  # the model proposes; it never acts
    assert [p["status"] for p in repo.proposals] == ["superseded", "pending"]
    add = repo.proposals[1]
    assert add["op"] == "add" and add["quest_id"] is None
    assert add["payload"]["quest"]["title"] == "Easy 3 km run"
    assert len(add["lines"]) == 2 * len(QUEST_TRIGGERS)
    assert add["run_id"] == str(repo.runs[0].id)
    quest_lines = [line for line in repo.lines if line.get("quest_id") == str(q.id)]
    assert len(quest_lines) == 2 * len(QUEST_TRIGGERS)
    assert "stale" not in {line["text"] for line in quest_lines}
    board_lines = [line for line in repo.lines if line.get("quest_id") is None]
    assert {line["trigger"] for line in board_lines} == set(BOARD_TRIGGERS)


def test_daily_am_prompt_carries_state_and_persona_voices() -> None:
    q = quest(title="Review notes", persona="teacher", category="learning", carries=3)
    repo = MemoryRepo(CONFIG)
    repo.quests = [q]
    provider = ScriptedProvider(
        plan([], [{"quest": str(q.id), "persona": "teacher", "lines": lines("teacher")}])
    )
    scheduler(repo, provider, NOW).evaluate(Trigger.tick)
    [request] = provider.requests
    assert "Quartermaster" in request.system and "carried 3 times" in request.system
    context = json.loads(request.prompt.split("\n\n", 1)[1])
    assert context["capacity_min"] == capacity_minutes(CONFIG, TODAY) == 60
    assert context["open_quests"][0]["carries"] == 3
    assert context["todays_board"] == [str(q.id)]
    assert context["goals"][0]["title"] == "Run a 10k"


def test_daily_pm_carries_over_without_a_model() -> None:
    q, done = quest(), quest(status="done", completed_at="2026-09-25T15:00:00Z")
    repo = MemoryRepo(CONFIG)
    repo.quests = [q, done]

    class Down(ScriptedProvider):
        def is_available(self) -> bool:
            return False

    evening = datetime(2026, 9, 25, 21, 0, tzinfo=BOGOTA)
    [pm] = [
        d
        for d in scheduler(repo, Down(), evening).evaluate(Trigger.tick)
        if d.job == JobName.daily_pm
    ]
    assert pm.status == Status.succeeded
    moved = repo.quests[0]
    assert (moved.scheduled_for, moved.carries) == (TODAY + timedelta(days=1), 1)
    assert repo.quests[1].status.value == "done"


def test_system_prompt_is_stable_for_caching() -> None:
    assert system_prompt(PACKS) == system_prompt(load_packs())
