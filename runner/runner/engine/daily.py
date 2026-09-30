"""daily_am and daily_pm.

daily_am (P0, LLM): reads the quest log, asks the provider chain for a DailyPlan, and caches the
result: proposed ops go to quest_proposals (the user decides), dialogue for existing quests goes
straight to persona_lines, dialogue for proposed adds rides with its proposal.

daily_pm (P0, code only): end-of-day accounting (forgotten days, carry-over) with the rules in
carry.py.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from questboard_schema.common_schema import JobName
from questboard_schema.config_schema import Config
from questboard_schema.daily_plan_schema import DailyPlan
from questboard_schema.quest_schema import Quest

from runner.engine.calibration import WINDOW_DAYS, calibration
from runner.engine.carry import carry_patch
from runner.engine.packs import Pack, load_packs
from runner.engine.prompts import system_prompt, user_prompt
from runner.engine.retro import REFLECTION_DAYS, reflection
from runner.engine.rollup import period_end, rollup, sub_quests
from runner.engine.validators import PlanContext, check_plan
from runner.providers.base import GenerationRequest, run_with_fallback
from runner.repo import ACTIVE
from runner.scheduler.core import JobContext, JobResult

HISTORY_DAYS = 14
OUTCOME_DAYS = 7
TIMEOUT_S = 600.0


def capacity_minutes(config: Config, day: date) -> int:
    hours = config.capacity.weekend_hours if day.weekday() >= 5 else config.capacity.weekday_hours
    return round(hours * 60 * config.capacity.focus_factor)


def _on_today(q: Quest, today: date) -> bool:
    """Active daily quests that the board shows today (including carry-overs)."""
    return (
        q.cadence.value == "daily"
        and q.status.value in ACTIVE
        and q.scheduled_for is not None
        and q.scheduled_for <= today
    )


def _quest_view(q: Quest) -> dict[str, Any]:
    view: dict[str, Any] = {
        "id": str(q.id),
        "title": q.title,
        "persona": q.persona.root,
        "cadence": q.cadence.value,
        "category": q.category.value,
        "status": q.status.value,
        "estimate_min": q.estimate_min,
        "priority": q.priority,
        "scheduled_for": q.scheduled_for,
        "carries": q.carries,
    }
    if q.deadline:
        view["deadline"] = q.deadline
        view["hard_deadline"] = q.hard_deadline
    if q.parent_id:
        view["parent_id"] = str(q.parent_id)
    return view


def period_work(quests: list[Quest], today: date) -> list[dict[str, Any]]:
    """Open weekly/monthly quests of the current period that still need a step today: no active
    daily sub-quest on today's board and work left that no open sub-quest carries. A monthly
    quest already split into weekly sub-quests is worked through those instead."""
    out = []
    for q in quests:
        end = period_end(q)
        if q.cadence.value == "daily" or q.status.value not in ACTIVE or end is None:
            continue
        if not (q.scheduled_for is not None and q.scheduled_for <= today <= end):
            continue
        subs = [s for s in sub_quests(q, quests) if s.status.value in ACTIVE]
        if any(_on_today(s, today) for s in subs):
            continue
        if any(s.cadence.value == "weekly" for s in subs):
            continue
        r = rollup(q, quests)
        if r.unplanned_min == 0:
            continue
        out.append(
            {
                "id": str(q.id),
                "title": q.title,
                "cadence": q.cadence.value,
                "persona": q.persona.root,
                "category": q.category.value,
                "priority": q.priority,
                "target_min": r.target_min,
                "done_min": r.done_min,
                "steps_done": r.done,
                "unplanned_min": r.unplanned_min,
                "days_left": (end - today).days + 1,
            }
        )
    return out


def _outcomes(quests: list[Quest], today: date) -> dict[str, Any]:
    since = today - timedelta(days=OUTCOME_DAYS)
    recent = [q for q in quests if q.scheduled_for and since <= q.scheduled_for < today]
    counts = Counter(q.status.value for q in recent)
    forgotten = sum(1 for q in quests for d in q.forgotten_on or [] if since <= d < today)
    return {
        "days": OUTCOME_DAYS,
        "by_status": dict(sorted(counts.items())),
        "forgotten_days": forgotten,
    }


def build_context(
    config: Config,
    quests: list[Quest],
    feedback: list[dict[str, Any]],
    today: date,
    reflection: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], PlanContext, list[str]]:
    open_quests = [q for q in quests if q.status.value in ACTIVE]
    todays = [q for q in open_quests if _on_today(q, today)]
    capacity = capacity_minutes(config, today)
    planned = sum(q.estimate_min for q in todays if q.status.value != "deferred")
    prompt_ctx = {
        "today": today.isoformat(),
        "weekday": today.strftime("%A"),
        "capacity_min": capacity,
        "today_planned_min": planned,
        "goals": [g.model_dump(mode="json", exclude_none=True) for g in config.goals],
        "open_quests": [_quest_view(q) for q in open_quests],
        "todays_board": [str(q.id) for q in todays],
        "period_work": period_work(quests, today),
        "recent_outcomes": _outcomes(quests, today),
        "estimate_calibration": calibration(quests, today),
        "recent_feedback": [
            {"action": f["action"], "quest_id": f.get("quest_id")} for f in feedback[-20:]
        ],
    }
    if reflection:
        prompt_ctx["reflection"] = reflection  # the user's latest answered retro
    plan_ctx = PlanContext(
        today=today,
        open_quests={
            str(q.id): {
                "persona": q.persona.root,
                "cadence": q.cadence.value,
                "estimate_min": q.estimate_min,
                "scheduled_for": q.scheduled_for,
            }
            for q in open_quests
        },
        personas=set(),
        capacity_min=capacity,
        today_planned_min=planned,
        quest_ids_needing_lines={str(q.id) for q in todays},
    )
    return prompt_ctx, plan_ctx, [str(q.id) for q in todays]


def write_plan(ctx: JobContext, plan: DailyPlan, todays_ids: list[str]) -> None:
    """Cache the plan: proposals for the user, dialogue for the app. No quest is changed."""
    repo = ctx.repo
    adds_seen = 0
    new_lines: dict[str, list[dict[str, Any]]] = {}
    existing_rows: list[dict[str, Any]] = []
    for bundle in plan.quest_lines:
        lines = [line.model_dump(mode="json") for line in bundle.lines]
        if bundle.quest.startswith("new:"):
            new_lines[bundle.quest] = lines
        else:
            existing_rows += [
                {
                    **line,
                    "quest_id": bundle.quest,
                    "persona": bundle.persona.root,
                    "run_id": ctx.run_id,
                }
                for line in lines
            ]

    proposals = []
    for wrapped in plan.diff.ops:
        op = wrapped.root
        row: dict[str, Any] = {
            "run_id": ctx.run_id,
            "op": op.op,
            "payload": op.model_dump(mode="json", exclude_unset=True),
        }
        if op.op == "add":
            row["quest_id"] = None
            row["lines"] = new_lines.get(f"new:{adds_seen}", [])
            adds_seen += 1
        else:
            row["quest_id"] = str(op.quest_id)
        proposals.append(row)

    # Yesterday's unanswered ideas give way to today's; weekly/monthly proposals stay put.
    repo.supersede_pending_proposals(JobName.daily_am)
    repo.insert_proposals(proposals)
    refreshed = sorted({r["quest_id"] for r in existing_rows} | set(todays_ids))
    repo.replace_quest_lines(refreshed, existing_rows)
    repo.replace_board_lines(
        [
            {
                **line.model_dump(mode="json"),
                "persona": line.persona.root,
                "quest_id": None,
                "run_id": ctx.run_id,
            }
            for line in plan.board_lines
        ]
    )


def daily_am(ctx: JobContext, packs: list[Pack] | None = None) -> JobResult:
    today = ctx.occurrence.date
    packs = packs if packs is not None else load_packs()
    quests = ctx.repo.list_quests(since=today - timedelta(days=WINDOW_DAYS))
    feedback = ctx.repo.list_feedback(since=today - timedelta(days=HISTORY_DAYS))
    past = reflection(ctx.repo.latest_answered_retro(today - timedelta(days=REFLECTION_DAYS)))
    prompt_ctx, plan_ctx, todays_ids = build_context(ctx.config, quests, feedback, today, past)
    plan_ctx = PlanContext(**{**plan_ctx.__dict__, "personas": {p.slug for p in packs}})
    request = GenerationRequest(
        job=ctx.occurrence.job,
        system=system_prompt(packs),
        prompt=user_prompt(prompt_ctx),
        timeout_s=TIMEOUT_S,
    )
    result = run_with_fallback(
        ctx.providers, request, DailyPlan, check=lambda plan: check_plan(plan, plan_ctx)
    )
    diff = result.output.diff
    write_plan(ctx, result.output, todays_ids)
    return JobResult(result.provider, result.usage, ops_count=len(diff.ops), summary=diff.summary)


def daily_pm(ctx: JobContext) -> JobResult:
    today = ctx.occurrence.date
    now: datetime = ctx.now
    for q in ctx.repo.list_quests(since=today - timedelta(days=HISTORY_DAYS)):
        patch = carry_patch(q, today, now)
        if patch:
            ctx.repo.update_quest(str(q.id), patch)
    return JobResult()
