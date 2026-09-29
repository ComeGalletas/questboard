from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.llm_run_schema import Status, Trigger
from questboard_schema.quest_diff_schema import QuestDiff

from runner.engine.carry import period_carry_patch
from runner.engine.period import (
    budget_minutes,
    check_period,
    needs_breakdown,
    period_for,
    period_job,
    slots,
)
from runner.engine.prompts import period_system_prompt, period_user_prompt
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


def ctx_for(open_quests, cadence="weekly", run_day=SUNDAY_DATE, planned=0, budget=600, today=None):
    period = period_for(cadence, run_day)
    today = today or run_day
    return {
        "period": period,
        "open": {str(q.id): q for q in open_quests},
        "personas": {p.slug for p in PACKS},
        "budget_min": budget,
        "planned_min": planned,
        "today": today,
        "slots": slots(CONFIG, period, open_quests, today),
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


def test_empty_weekly_diff_keeps_the_summary_on_the_run() -> None:
    summary = "The gym quest already covers the week; nothing else fits the budget."
    provider = ScriptedProvider({"ops": [], "summary": summary})
    repo = MemoryRepo(CONFIG)
    sched = Scheduler(
        repo=repo,
        handlers={JobName.weekly: lambda c: period_job("weekly", c, PACKS)},
        providers={ProviderName.claude_cli: provider},
        clock=lambda: SUNDAY.astimezone(UTC),
    )
    [d] = sched.evaluate(Trigger.tick)
    assert (d.status, d.reason) == (Status.succeeded, "ok, 0 ops")
    assert repo.proposals == []
    [run] = repo.runs
    assert (run.ops_count, run.summary) == (0, summary)


def test_summary_is_checked_for_personal_data() -> None:
    leaky = QuestDiff.model_validate({"ops": [], "summary": "Call me at 300 555 1234 first."})
    assert any("summary" in p and "long number" in p for p in check_period(leaky, ctx_for([])))
    ok = QuestDiff.model_validate({"ops": [], "summary": "Goals are covered."})
    assert check_period(ok, ctx_for([])) == []


@pytest.mark.parametrize(("cadence", "sub"), [("weekly", "daily"), ("monthly", "weekly")])
def test_period_prompt_asks_for_goal_coverage(cadence: str, sub: str) -> None:
    system = " ".join(period_system_prompt(PACKS, cadence).split())
    # Uncovered goals should get adds; empty is only for covered goals or a used budget.
    assert f"For every goal that no open quest covers, add a {cadence} quest" in system
    assert "An empty ops list is right only when every goal is already covered" in system
    assert "an empty list is fine" not in system
    assert "Always write summary" in system
    assert f"{sub} sub-quests" in system
    # Sub-quests are planned against each day's (week's) room, not the period budget.
    assert f"{sub} sub-quests do NOT count against budget_min" in system
    assert "needs_breakdown" in system
    assert "lower its estimate_min" not in system
    prompt = period_user_prompt(cadence, {"budget_min": 600})
    assert prompt.startswith(f"Current state (JSON). Propose the {cadence} diff for this period.")
    assert "today's diff and dialogue" not in prompt


# -- sub-quests: daily capacity, not the weekly budget ----------------------------------------


def step(parent, day: str, minutes: int = 60, cadence: str = "daily"):
    return add(
        cadence=cadence,
        title="Gym session",
        parent_id=str(parent.id),
        scheduled_for=day,
        estimate_min=minutes,
    )


def test_sub_quests_use_each_days_capacity_not_the_weekly_budget() -> None:
    # The real first run: two weekly quests nearly fill the budget; the breakdown still fits.
    gym = quest(cadence="weekly", scheduled_for="2026-09-28", title="Gym", estimate_min=120)
    code = quest(cadence="weekly", scheduled_for="2026-09-28", title="Code", estimate_min=110)
    ctx = ctx_for([gym, code], planned=230, budget=240)
    week = [step(gym, d) for d in ("2026-09-28", "2026-09-30", "2026-10-03")]
    assert check_period(diff(*week), ctx) == []
    # Over budget already (e.g. after a config change): steps and an empty diff still pass.
    assert check_period(diff(*week), {**ctx, "budget_min": 200}) == []
    assert check_period(diff(), {**ctx, "budget_min": 200}) == []
    # ...but a diff that grows the weekly total does not.
    assert any("against a budget" in p for p in check_period(diff(add()), ctx))

    # Weekday capacity is 60 min (2 h x 0.5): two steps on Monday don't fit.
    crowded = diff(step(gym, "2026-09-28"), step(code, "2026-09-28", 45))
    [problem] = check_period(crowded, ctx)
    assert "daily sub-quests on 2026-09-28 bring it to 105 min against 60 min" in problem

    # Daily quests already on a day count too.
    busy_tuesday = quest(scheduled_for="2026-09-29", estimate_min=50)
    problems = check_period(diff(step(gym, "2026-09-29", 30)), ctx_for([gym, busy_tuesday]))
    assert any("on 2026-09-29 bring it to 80 min" in p for p in problems)


def test_sub_quests_are_not_scheduled_before_today() -> None:
    # A forced re-run on Wednesday of the current week (the latest occurrence is Sunday's).
    gym = quest(cadence="weekly", scheduled_for="2026-09-28", estimate_min=240)
    ctx = ctx_for([gym], today=date(2026, 9, 30))
    assert sorted(ctx["slots"]) == [date(2026, 9, 30)] + [date(2026, 10, d) for d in range(1, 5)]
    problems = check_period(diff(step(gym, "2026-09-29"), step(gym, "2026-10-01")), ctx)
    assert problems == ["ops[0]: sub-quests may not be scheduled before today"]


def test_monthly_sub_quests_use_each_weeks_budget() -> None:
    goal = quest(cadence="monthly", scheduled_for="2026-10-01", estimate_min=600)
    ctx = ctx_for([goal], cadence="monthly", run_day=date(2026, 10, 1))
    mondays = [date(2026, 10, d) for d in (5, 12, 19, 26)]
    assert sorted(ctx["slots"]) == mondays
    week_budget = ctx["slots"][mondays[0]]["capacity_min"]
    assert week_budget == budget_minutes(CONFIG, period_for("weekly", date(2026, 10, 4)))
    ok = diff(*(step(goal, d.isoformat(), 90, cadence="weekly") for d in mondays))
    assert check_period(ok, ctx) == []
    big = diff(step(goal, "2026-10-05", week_budget * 2, cadence="weekly"))
    assert any("weekly sub-quests on 2026-10-05" in p for p in check_period(big, ctx))
    tuesday = diff(step(goal, "2026-10-06", 90, cadence="weekly"))
    assert any("on a Monday" in p for p in check_period(tuesday, ctx))


def test_needs_breakdown_lists_period_quests_without_open_sub_quests() -> None:
    period = period_for("weekly", SUNDAY_DATE)
    split = quest(cadence="weekly", scheduled_for="2026-09-28", title="Split", estimate_min=240)
    whole = quest(cadence="weekly", scheduled_for="2026-09-28", title="Whole", estimate_min=300)
    done_sub = quest(parent_id=str(whole.id), status="done", actual_min=100, completed_at=None)
    old = quest(cadence="weekly", scheduled_for="2026-09-21", title="Last week")
    quests = [split, whole, old, done_sub, quest(parent_id=str(split.id), scheduled_for=None)]
    assert needs_breakdown(period, quests) == [
        {"id": str(whole.id), "title": "Whole", "remaining_min": 200}
    ]


def test_weekly_job_asks_for_the_breakdown_with_room_per_day() -> None:
    gym = quest(cadence="weekly", scheduled_for="2026-09-28", title="Gym", estimate_min=120)
    repo = MemoryRepo(CONFIG)
    repo.quests = [gym]
    provider = ScriptedProvider(
        {"ops": [step(gym, "2026-09-28"), step(gym, "2026-10-01")], "summary": "Two sessions."}
    )
    sched = Scheduler(
        repo=repo,
        handlers={JobName.weekly: lambda c: period_job("weekly", c, PACKS)},
        providers={ProviderName.claude_cli: provider},
        clock=lambda: SUNDAY.astimezone(UTC),
    )
    [d] = sched.evaluate(Trigger.tick)
    assert (d.status, d.reason) == (Status.succeeded, "ok, 2 ops"), d.reason
    context = json.loads(provider.requests[0].prompt.split("\n\n", 1)[1])
    assert context["today"] == "2026-09-27"
    assert context["needs_breakdown"] == [{"id": str(gym.id), "title": "Gym", "remaining_min": 120}]
    assert [(x["date"], x["capacity_min"]) for x in context["days"]][:1] == [("2026-09-28", 60)]
    assert len(context["days"]) == 7
    assert [p["payload"]["quest"]["parent_id"] for p in repo.proposals] == [str(gym.id)] * 2
