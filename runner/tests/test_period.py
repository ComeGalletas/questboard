from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.llm_run_schema import Status, Trigger
from questboard_schema.quest_diff_schema import QuestDiff

from runner.engine.carry import period_carry_patch
from runner.engine.period import budget_minutes, check_period, period_for, period_job
from runner.repo import MemoryRepo
from runner.scheduler.core import Scheduler

sys.path.insert(0, str(Path(__file__).parent))
from test_engine import CONFIG, PACKS, ScriptedProvider, quest  # noqa: E402

BOGOTA = ZoneInfo("America/Bogota")
SUNDAY = datetime(2026, 9, 27, 18, 0, tzinfo=BOGOTA)
NEXT_MONDAY = date(2026, 9, 28)
SUNDAY_DATE = SUNDAY.date()


def test_periods() -> None:
    week = period_for("weekly", SUNDAY.date())
    assert (week.start, week.end) == (NEXT_MONDAY, date(2026, 10, 4))
    month = period_for("monthly", date(2026, 10, 1))
    assert (month.start, month.end) == (date(2026, 10, 1), date(2026, 10, 31))
    # weekday 2 h x 0.5 focus = 60 min, weekend 5 h x 0.5 = 150 min
    assert budget_minutes(CONFIG, week) == round((5 * 60 + 2 * 150) * 0.4)


def test_weekly_carry_cap_and_hard_deadlines() -> None:
    last_week = "2026-09-21"
    open_weekly = quest(cadence="weekly", scheduled_for=last_week, carries=1)
    assert period_carry_patch(open_weekly, NEXT_MONDAY, SUNDAY)["carries"] == 2
    capped = quest(cadence="weekly", scheduled_for=last_week, carries=2)
    assert period_carry_patch(capped, NEXT_MONDAY, SUNDAY)["status"] == "abandoned"
    hard = quest(cadence="weekly", scheduled_for=last_week, carries=4, hard_deadline=True)
    assert period_carry_patch(hard, NEXT_MONDAY, SUNDAY)["scheduled_for"] == "2026-09-28"
    assert period_carry_patch(quest(scheduled_for=last_week), NEXT_MONDAY, SUNDAY) is None


def ctx_for(open_quests, cadence="weekly", run_day=SUNDAY_DATE, planned=0, budget=600):
    return {
        "period": period_for(cadence, run_day),
        "open": {str(q.id): q for q in open_quests},
        "personas": {p.slug for p in PACKS},
        "budget_min": budget,
        "planned_min": planned,
    }


def add(**quest_fields):
    base = {
        "title": "Long run",
        "persona": "coach",
        "cadence": "weekly",
        "category": "health",
        "estimate_min": 90,
        "priority": 2,
        "scheduled_for": "2026-09-28",
    }
    return {"op": "add", "reason": "goal", "quest": {**base, **quest_fields}}


def diff(*ops) -> QuestDiff:
    return QuestDiff.model_validate({"ops": list(ops)})


def test_period_rules() -> None:
    parent = quest(cadence="weekly", scheduled_for="2026-09-28", title="Write report")
    ok = diff(
        add(),
        add(
            cadence="daily",
            title="Draft intro",
            parent_id=str(parent.id),
            scheduled_for="2026-09-30",
            estimate_min=30,
        ),
    )
    assert check_period(ok, ctx_for([parent])) == []

    bad = diff(
        add(scheduled_for="2026-10-05"),
        add(cadence="daily", scheduled_for="2026-09-29"),  # no parent
        add(cadence="monthly"),
        add(category="subscription"),
        add(estimate_min=900),
    )
    problems = "\n".join(check_period(bad, ctx_for([parent])))
    assert "adds are scheduled for 2026-09-28" in problems
    assert "sub-quests need an open weekly parent" in problems
    assert "only adds weekly or daily" in problems
    assert "extractors only" in problems
    assert "against a budget of 600" in problems

    split_and_drop = diff(
        add(cadence="daily", parent_id=str(parent.id), scheduled_for="2026-09-29", estimate_min=30),
        {"op": "drop", "quest_id": str(parent.id), "reason": "split"},
    )
    assert any(
        "keep a quest you split open" in p for p in check_period(split_and_drop, ctx_for([parent]))
    )


def test_weekly_job_carries_then_proposes() -> None:
    carried = quest(cadence="weekly", scheduled_for="2026-09-21", title="Read a chapter")
    repo = MemoryRepo(CONFIG)
    repo.quests = [carried]
    output = {
        "ops": [
            add(),
            {
                "op": "update",
                "quest_id": str(carried.id),
                "reason": "carried once",
                "changes": {"estimate_min": 30},
            },
        ]
    }
    provider = ScriptedProvider(output)
    sched = Scheduler(
        repo=repo,
        handlers={JobName.weekly: lambda c: period_job("weekly", c, PACKS)},
        providers={ProviderName.claude_cli: provider},
        clock=lambda: SUNDAY.astimezone(UTC),
    )
    [d] = sched.evaluate(Trigger.tick)
    assert d.status == Status.succeeded, d.reason
    moved = repo.quests[0]
    assert (moved.scheduled_for, moved.carries) == (NEXT_MONDAY, 1)
    assert [p["op"] for p in repo.proposals] == ["add", "update"]
    assert repo.quests[0].estimate_min == carried.estimate_min  # proposals only
    assert "plan the weekly quests" in provider.requests[0].system
