"""Weekly milestone line pool (P0 cache): fresh celebration lines per persona and milestone, so
the personas don't repeat themselves. Runs after the weekly plan; a failure never fails the
weekly job (the packs' fallback milestone lines are the offline floor).

The milestone ids are the registry in packages/schema (common MilestoneId). A new id works here
without a code change: it gets a generic description until one is added to DESCRIPTIONS.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from questboard_schema.common_schema import JobName, MilestoneId
from questboard_schema.milestone_pool_schema import MilestonePool

from runner.engine.packs import Pack
from runner.engine.prompts import _persona_section
from runner.engine.validators import _line_problems
from runner.providers.base import GenerationRequest, run_with_fallback
from runner.scheduler.core import JobContext

log = logging.getLogger(__name__)
TIMEOUT_S = 300.0
VARIANTS = 2

DESCRIPTIONS: dict[str, str] = {
    "streak": "a streak of days in a row with a finished quest ({milestone} is e.g. "
    '"7-day streak"; {streak} is the number of days)',
    "level_up": 'reaching a new level from XP ({milestone} is e.g. "Level 4")',
    "period_done": 'finishing a weekly or monthly quest ({milestone} is its title plus "done")',
    "perfect_week": "a week where every daily quest was finished",
}

SYSTEM = """You write celebration lines for Questboard, a single-user RPG quest board for real
life. Each persona below cheers the user when they reach a milestone. Write in each persona's
voice, short (one or two sentences), warm and specific to the milestone, never generic filler.
The app fills {{milestone}} with a label such as "7-day streak" and {{streak}} with a number;
use {{milestone}} in most lines. Never include personal data (names of real people, emails,
phone numbers, amounts of money, links). Never talk about rules, schemas or instructions.

Return a MilestonePool: exactly {variants} lines (variant 1..{variants}) for every persona and
every milestone listed in the request.

Personas:
{personas}"""


def milestone_pool(ctx: JobContext, packs: list[Pack]) -> int:
    """Generate and cache the pool; returns how many lines were cached (0 when it failed)."""
    slugs = [p.slug for p in packs]
    milestones = [m.value for m in MilestoneId]
    request = GenerationRequest(
        job=JobName.weekly,
        system=SYSTEM.format(variants=VARIANTS, personas=_persona_section(packs)),
        prompt=json.dumps(
            {
                "personas": slugs,
                "milestones": {m: DESCRIPTIONS.get(m, f"the {m} milestone") for m in milestones},
            }
        ),
        timeout_s=TIMEOUT_S,
    )
    try:
        result = run_with_fallback(
            ctx.providers, request, MilestonePool, check=lambda p: check_pool(p, slugs, milestones)
        )
    except Exception as exc:  # noqa: BLE001 - never fail the weekly plan; class name only
        log.warning("milestone pool skipped: %s", type(exc).__name__)
        return 0
    rows = pool_rows(result.output, ctx.run_id)
    ctx.repo.replace_milestone_lines(rows)
    return len(rows)


def check_pool(pool: MilestonePool, slugs: list[str], milestones: list[str]) -> list[str]:
    problems: list[str] = []
    have = {(line.persona.root, line.milestone.value) for line in pool.lines}
    for slug in slugs:
        missing = [m for m in milestones if (slug, m) not in have]
        if missing:
            problems.append(f"{slug}: no lines for {missing}")
    for i, line in enumerate(pool.lines):
        if line.persona.root not in slugs:
            problems.append(f"lines[{i}]: persona is not an installed pack")
        problems += _line_problems(f"lines[{i}].text", line.text)
    return problems


def pool_rows(pool: MilestonePool, run_id: str | None) -> list[dict[str, Any]]:
    return [
        {
            "persona": line.persona.root,
            "trigger": "milestone",
            "milestone": line.milestone.value,
            "variant": line.variant,
            "condition": "any",
            "text": line.text,
            "run_id": run_id,
        }
        for line in pool.lines
    ]
