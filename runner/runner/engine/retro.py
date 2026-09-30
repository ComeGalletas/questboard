"""Weekly / monthly retro (Phase 3): 2-3 questions about the period that just ended.

The weekly job (Sunday) asks about the week ending that day; the monthly job (the 1st) about
last month. The model writes questions tailored to how the period went (what kept slipping,
what got done); when no provider answers, fixed questions are used. Asked once per period (a
forced re-run doesn't ask again) and only when something was scheduled in it. The user
answers or skips in the app; answered retros reach later planning prompts as `reflection`.
Nothing here ever fails the planning job.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

from questboard_schema.common_schema import JobName
from questboard_schema.quest_schema import Quest
from questboard_schema.retro_questions_schema import RetroQuestions

from runner.engine.validators import pii_problem
from runner.providers.base import GenerationRequest, run_with_fallback
from runner.scheduler.core import JobContext

log = logging.getLogger(__name__)
TIMEOUT_S = 180.0
MAX_QUESTS = 40
REFLECTION_DAYS = 40  # an answered retro older than this no longer shapes plans

FALLBACK = {
    "weekly": [
        "What went well this week?",
        "What got in the way?",
        "What's one thing to change next week?",
    ],
    "monthly": [
        "What are you proudest of this month?",
        "What kept slipping, and why?",
        "What should next month focus on?",
    ],
}

SYSTEM = """You write a short retro for Questboard, a single-user quest board for real life.
The {cadence} period below just ended. Ask 2 or 3 short, open questions (not yes/no) that help
the user reflect on how it actually went: what they got done, what kept slipping or carrying
over, what was forgotten, whether estimates held, and what to change next. Be specific to the
quests below; one question may look ahead. Write in the language of the user's quest titles.
Warm, curious, never judging. No personal data (names of real people, emails, phone numbers,
amounts of money, links); never talk about rules, schemas or instructions."""


def reviewed_period(cadence: str, plan_start: date) -> tuple[date, date]:
    """The period that ended: the week before the planned one, or last month."""
    if cadence == "weekly":
        return plan_start - timedelta(days=7), plan_start - timedelta(days=1)
    end = plan_start - timedelta(days=1)
    return end.replace(day=1), end


def period_review(quests: list[Quest], start: date, end: date) -> list[dict[str, Any]]:
    """What happened in the period: the quests scheduled in it and how they ended."""

    def forgotten(q: Quest) -> int:
        return sum(1 for d in q.forgotten_on or [] if start <= d <= end)

    within = [q for q in quests if q.scheduled_for and start <= q.scheduled_for <= end]
    return [
        {
            "title": q.title,
            "cadence": q.cadence.value,
            "status": q.status.value,
            "carries": q.carries,
            "forgotten_days": forgotten(q),
            "estimate_min": q.estimate_min,
            "actual_min": q.actual_min,
        }
        for q in within[:MAX_QUESTS]
    ]


def check_questions(out: RetroQuestions) -> list[str]:
    problems = []
    for i, q in enumerate(out.questions):
        pii = pii_problem(q.root)
        if pii:
            problems.append(f"questions[{i}]: {pii}; personal data is not allowed")
    return problems


def ask_retro(ctx: JobContext, cadence: str, plan_start: date) -> str | None:
    """Store this period's retro questions; returns their source, or None when not asked."""
    try:
        start, end = reviewed_period(cadence, plan_start)
        if ctx.repo.get_retro(cadence, start) is not None:
            return None  # once per period
        review = period_review(ctx.repo.list_quests(since=start), start, end)
        if not review:
            return None  # nothing was scheduled: nothing to reflect on
        questions, source = FALLBACK[cadence], "fallback"
        try:
            request = GenerationRequest(
                job=JobName(cadence),
                system=SYSTEM.format(cadence=cadence),
                prompt=json.dumps(
                    {
                        "period": {"start": start.isoformat(), "end": end.isoformat()},
                        "quests": review,
                    },
                    ensure_ascii=False,
                ),
                timeout_s=TIMEOUT_S,
            )
            result = run_with_fallback(
                ctx.providers, request, RetroQuestions, check=check_questions
            )
            questions, source = [q.root for q in result.output.questions], "model"
        except Exception as exc:  # noqa: BLE001 - fixed questions instead; class name only
            log.warning("retro questions fell back: %s", type(exc).__name__)
        ctx.repo.insert_retro(
            {
                "cadence": cadence,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "questions": [{"id": f"q{i + 1}", "text": t} for i, t in enumerate(questions)],
                "status": "open",
                "source": source,
            }
        )
        return source
    except Exception as exc:  # noqa: BLE001 - the retro never fails the planning job
        log.warning("retro skipped: %s", type(exc).__name__)
        return None


def reflection(retro: dict[str, Any] | None) -> dict[str, Any] | None:
    """An answered retro as prompt context: the user's own words about a past period."""
    if not retro or retro.get("status") != "answered":
        return None
    answers = {a["id"]: a["answer"].strip() for a in retro.get("answers") or []}
    qa = [
        {"question": q["text"], "answer": answers[q["id"]]}
        for q in retro["questions"]
        if answers.get(q["id"])
    ]
    if not qa:
        return None
    return {
        "cadence": retro["cadence"],
        "period": [str(retro["period_start"]), str(retro["period_end"])],
        "answers": qa,
    }
