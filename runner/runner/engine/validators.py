"""Rules a DailyPlan must satisfy beyond its schema. Problems name paths, never values, so they
can go back to the model (retry) and into llm_runs.error without leaking data."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from questboard_schema.daily_plan_schema import DailyPlan

QUEST_TRIGGERS = [
    "assigned",
    "reminder_am",
    "reminder_mid",
    "reminder_pm",
    "started",
    "completed_early",
    "completed_on_time",
    "completed_late",
    "partial",
    "snoozed",
    "deferred",
    "skipped",
    "forgotten",
    "overdue_1d",
    "overdue_3d",
    "overdue_7d",
    "carried_over",
    "abandoned",
]
BOARD_TRIGGERS = ("all_done", "half_by_noon", "nothing_by_15", "over_capacity")
PLACEHOLDERS = {"time_left", "streak", "days_carried", "actual_vs_estimate", "next_quest"}
# Invariant 4: money enters only through deterministic extractors.
MONEY_CATEGORIES = {"utilities", "subscription"}
CAPACITY_SLACK = 1.15

PII_PATTERNS = {
    "an email address": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "a long number (phone, ID or card)": re.compile(r"\d[\d .-]{6,}\d"),
    "a URL": re.compile(r"https?://|www\.", re.I),
}


@dataclass(frozen=True)
class PlanContext:
    today: date
    open_quests: dict[str, dict]  # id -> {persona, cadence, estimate_min, scheduled_for}
    personas: set[str]
    capacity_min: int
    today_planned_min: int  # open daily quests already on today's board
    quest_ids_needing_lines: set[str] = field(default_factory=set)


def pii_problem(text: str) -> str | None:
    for label, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            return f"contains {label}"
    return None


def _line_problems(path: str, text: str) -> list[str]:
    problems = []
    unknown = set(re.findall(r"\{(\w+)\}", text)) - PLACEHOLDERS
    if unknown:
        problems.append(f"{path}: unknown placeholder(s) {sorted(unknown)}")
    pii = pii_problem(text)
    if pii:
        problems.append(f"{path}: {pii}; personal data is not allowed in dialogue")
    return problems


def check_plan(plan: DailyPlan, ctx: PlanContext) -> list[str]:
    problems: list[str] = []
    adds = []
    planned = ctx.today_planned_min
    for i, wrapped in enumerate(plan.diff.ops):
        op = wrapped.root
        path = f"diff.ops[{i}]"
        if op.op == "add":
            adds.append(op)
            q = op.quest
            if q.persona.root not in ctx.personas:
                problems.append(f"{path}: persona is not an installed pack")
            if q.category.value in MONEY_CATEGORIES:
                problems.append(
                    f"{path}: {q.category.value} quests come from extractors only; do not add them"
                )
            if q.deadline is not None:
                problems.append(f"{path}: adds may not set a deadline; use scheduled_for")
            if q.cadence.value == "daily" and q.scheduled_for not in (None, ctx.today):
                problems.append(f"{path}: daily adds must be scheduled for today")
            if q.cadence.value == "daily":
                planned += q.estimate_min
            problems += _line_problems(f"{path}.quest.title", q.title)
            continue
        qid = str(op.quest_id)
        existing = ctx.open_quests.get(qid)
        if existing is None:
            problems.append(f"{path}: quest_id is not an open quest")
            continue
        today_daily = existing["cadence"] == "daily" and existing["scheduled_for"] == ctx.today
        if op.op == "drop":
            if today_daily:
                planned -= existing["estimate_min"]
            continue
        changes = op.changes
        if changes.deadline is not None or "deadline" in changes.model_fields_set:
            problems.append(f"{path}: the model may not change deadlines")
        if changes.persona is not None and changes.persona.root not in ctx.personas:
            problems.append(f"{path}: persona is not an installed pack")
        if changes.title is not None:
            problems += _line_problems(f"{path}.changes.title", changes.title)
        if today_daily and changes.estimate_min is not None:
            planned += changes.estimate_min - existing["estimate_min"]

    if planned > ctx.capacity_min * CAPACITY_SLACK:
        problems.append(
            f"today's plan is {planned} min against {ctx.capacity_min} min of capacity; "
            "drop or defer quests until it fits"
        )

    covered: set[str] = set()
    for i, bundle in enumerate(plan.quest_lines):
        path = f"quest_lines[{i}]"
        ref = bundle.quest
        if ref.startswith("new:"):
            n = int(ref[4:])
            if n >= len(adds):
                problems.append(f"{path}: {ref} does not match an add op")
                continue
            persona = adds[n].quest.persona.root
        elif ref in ctx.open_quests:
            persona = ctx.open_quests[ref]["persona"]
        else:
            problems.append(f"{path}: quest is neither an open quest nor new:N")
            continue
        covered.add(ref)
        if bundle.persona.root != persona:
            problems.append(f"{path}: persona must be the quest's persona")
        triggers = {line.trigger.value for line in bundle.lines}
        missing = [t for t in QUEST_TRIGGERS if t not in triggers]
        if missing:
            problems.append(f"{path}: missing triggers {missing}")
        for j, line in enumerate(bundle.lines):
            problems += _line_problems(f"{path}.lines[{j}]", line.text)

    wanted = ctx.quest_ids_needing_lines | {f"new:{n}" for n in range(len(adds))}
    for ref in sorted(wanted - covered):
        label = ref if ref.startswith("new:") else "an open quest on today's board"
        problems.append(f"quest_lines: no dialogue for {label} ({ref})")

    board = {line.trigger.value for line in plan.board_lines}
    missing_board = [t for t in BOARD_TRIGGERS if t not in board]
    if missing_board:
        problems.append(f"board_lines: missing triggers {missing_board}")
    for i, line in enumerate(plan.board_lines):
        if line.persona.root not in ctx.personas:
            problems.append(f"board_lines[{i}]: persona is not an installed pack")
        problems += _line_problems(f"board_lines[{i}]", line.text)
    return problems
