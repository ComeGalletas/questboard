"""weekly (Sun 18:00, plans the coming week) and monthly (1st 08:00, plans this month).

Both: carry open quests of that cadence into the new period (code), then ask the provider chain
for a QuestDiff for the period and store it as proposals. The model may break an open quest of
the job's cadence into sub-quests one level down (weekly -> daily, monthly -> weekly) via
parent_id. Nothing is applied until the user accepts (invariant 3).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from questboard_schema.config_schema import Config
from questboard_schema.quest_diff_schema import QuestDiff
from questboard_schema.quest_schema import Quest

from runner.engine.calibration import WINDOW_DAYS, calibration
from runner.engine.carry import period_carry_patch
from runner.engine.daily import HISTORY_DAYS, _outcomes, _quest_view, capacity_minutes
from runner.engine.packs import Pack, load_packs
from runner.engine.prompts import period_system_prompt, user_prompt
from runner.engine.validators import MONEY_CATEGORIES, _line_problems
from runner.providers.base import GenerationRequest, run_with_fallback
from runner.repo import ACTIVE
from runner.scheduler.core import JobContext, JobResult

# Share of the period's free time the longer-horizon quests may claim; dailies use the rest.
BUDGET_SHARE = {"weekly": 0.4, "monthly": 0.25}
SUB_CADENCE = {"weekly": "daily", "monthly": "weekly"}
TIMEOUT_S = 600.0


@dataclass(frozen=True)
class Period:
    cadence: str  # "weekly" | "monthly"
    start: date
    end: date  # inclusive

    def days(self) -> list[date]:
        return [self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1)]


def period_for(cadence: str, run_day: date) -> Period:
    if cadence == "weekly":  # runs Sunday evening for the week starting tomorrow
        start = run_day + timedelta(days=(7 - run_day.weekday()) % 7 or 7)
        return Period("weekly", start, start + timedelta(days=6))
    start = run_day.replace(day=1)
    last = calendar.monthrange(start.year, start.month)[1]
    return Period("monthly", start, start.replace(day=last))


def budget_minutes(config: Config, period: Period) -> int:
    total = sum(capacity_minutes(config, d) for d in period.days())
    return round(total * BUDGET_SHARE[period.cadence])


def check_period(diff: QuestDiff, ctx: dict[str, Any]) -> list[str]:
    period: Period = ctx["period"]
    open_q: dict[str, Quest] = ctx["open"]
    sub = SUB_CADENCE[period.cadence]
    problems: list[str] = []
    planned = ctx["planned_min"]
    for i, wrapped in enumerate(diff.ops):
        op = wrapped.root
        path = f"ops[{i}]"
        if op.op == "add":
            q = op.quest
            cad = q.cadence.value
            if q.persona.root not in ctx["personas"]:
                problems.append(f"{path}: persona is not an installed pack")
            if q.category.value in MONEY_CATEGORIES:
                problems.append(f"{path}: {q.category.value} quests come from extractors only")
            if q.deadline is not None:
                problems.append(f"{path}: adds may not set a deadline; use scheduled_for")
            if cad == period.cadence:
                if q.parent_id is not None:
                    problems.append(f"{path}: {cad} quests have no parent")
                if q.scheduled_for not in (None, period.start):
                    problems.append(f"{path}: {cad} adds are scheduled for {period.start}")
                planned += q.estimate_min
            elif cad == sub:
                parent = open_q.get(str(q.parent_id)) if q.parent_id else None
                if parent is None or parent.cadence.value != period.cadence:
                    problems.append(
                        f"{path}: {cad} sub-quests need an open {period.cadence} parent"
                    )
                if q.scheduled_for is None or not period.start <= q.scheduled_for <= period.end:
                    problems.append(f"{path}: sub-quests must be scheduled inside the period")
                if sub == "weekly" and q.scheduled_for and q.scheduled_for.weekday() != 0:
                    problems.append(f"{path}: weekly sub-quests are scheduled on a Monday")
            else:
                problems.append(f"{path}: this job only adds {period.cadence} or {sub} quests")
            problems += _line_problems(f"{path}.quest.title", q.title)
            continue
        existing = open_q.get(str(op.quest_id))
        if existing is None or existing.cadence.value != period.cadence:
            problems.append(f"{path}: quest_id is not an open {period.cadence} quest")
            continue
        if op.op == "drop":
            planned -= existing.estimate_min
            continue
        if op.changes.deadline is not None or "deadline" in op.changes.model_fields_set:
            problems.append(f"{path}: the model may not change deadlines")
        if op.changes.estimate_min is not None:
            planned += op.changes.estimate_min - existing.estimate_min
    parents = {
        str(w.root.quest.parent_id)
        for w in diff.ops
        if w.root.op == "add" and w.root.quest.parent_id is not None
    }
    for i, wrapped in enumerate(diff.ops):
        op = wrapped.root
        if op.op == "drop" and str(op.quest_id) in parents:
            problems.append(f"ops[{i}]: keep a quest you split open; its sub-quests belong to it")
    if planned > ctx["budget_min"]:
        problems.append(
            f"{period.cadence} plan is {planned} min against a budget of {ctx['budget_min']} min; "
            "drop or shrink quests"
        )
    return problems


def _write(ctx: JobContext, diff: QuestDiff) -> None:
    rows = []
    for wrapped in diff.ops:
        op = wrapped.root
        rows.append(
            {
                "run_id": ctx.run_id,
                "op": op.op,
                "payload": op.model_dump(mode="json", exclude_unset=True),
                "quest_id": None if op.op == "add" else str(op.quest_id),
                "lines": [],
            }
        )
    ctx.repo.insert_proposals(rows)


def period_job(cadence: str, ctx: JobContext, packs: list[Pack] | None = None) -> JobResult:
    period = period_for(cadence, ctx.occurrence.date)
    packs = packs if packs is not None else load_packs()
    repo = ctx.repo

    # 1. Carry-over (code): open quests of this cadence move into the new period.
    for q in repo.list_quests(since=period.start - timedelta(days=HISTORY_DAYS)):
        patch = period_carry_patch(q, period.start, ctx.now)
        if patch:
            repo.update_quest(str(q.id), patch)

    # 2. Proposals (model): the period's quests, within budget.
    quests = repo.list_quests(since=period.start - timedelta(days=WINDOW_DAYS))
    open_q = {str(q.id): q for q in quests if q.status.value in ACTIVE}
    in_period = [
        q for q in open_q.values() if q.cadence.value == cadence and q.scheduled_for == period.start
    ]
    budget = budget_minutes(ctx.config, period)
    planned = sum(q.estimate_min for q in in_period)
    prompt_ctx = {
        "period": {"cadence": cadence, "start": period.start, "end": period.end},
        "budget_min": budget,
        "planned_min": planned,
        "goals": [g.model_dump(mode="json", exclude_none=True) for g in ctx.config.goals],
        "open_quests": [_quest_view(q) for q in open_q.values()],
        "recent_outcomes": _outcomes(quests, period.start),
        "estimate_calibration": calibration(quests, period.start),
    }
    check_ctx = {
        "period": period,
        "open": open_q,
        "personas": {p.slug for p in packs},
        "budget_min": budget,
        "planned_min": planned,
    }
    request = GenerationRequest(
        job=ctx.occurrence.job,
        system=period_system_prompt(packs, cadence),
        prompt=user_prompt(prompt_ctx),
        timeout_s=TIMEOUT_S,
    )
    result = run_with_fallback(
        ctx.providers, request, QuestDiff, check=lambda d: check_period(d, check_ctx)
    )
    _write(ctx, result.output)
    return JobResult(result.provider, result.usage)


def weekly(ctx: JobContext) -> JobResult:
    return period_job("weekly", ctx)


def monthly(ctx: JobContext) -> JobResult:
    return period_job("monthly", ctx)
