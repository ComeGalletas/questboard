"""Weekly milestone line pool: cached after the weekly plan, never fails it."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from questboard_schema.common_schema import JobName, MilestoneId, ProviderName
from questboard_schema.llm_run_schema import Status, Trigger
from questboard_schema.milestone_pool_schema import MilestonePool

from runner.engine.milestone_pool import check_pool
from runner.engine.period import period_job
from runner.repo import MemoryRepo
from runner.scheduler.core import Scheduler

sys.path.insert(0, str(Path(__file__).parent))
from test_engine import CONFIG, PACKS, ScriptedProvider  # noqa: E402

SUNDAY = datetime(2026, 9, 27, 18, 0, tzinfo=ZoneInfo("America/Bogota"))
SLUGS = [p.slug for p in PACKS]
MILESTONES = [m.value for m in MilestoneId]


def full_pool(text: str = "Big moment: {milestone}.") -> dict:
    return {
        "lines": [
            {"persona": s, "milestone": m, "variant": v, "text": text}
            for s in SLUGS
            for m in MILESTONES
            for v in (1, 2)
        ]
    }


def weekly(repo: MemoryRepo, provider: ScriptedProvider) -> Scheduler:
    return Scheduler(
        repo=repo,
        handlers={JobName.weekly: lambda c: period_job("weekly", c, PACKS)},
        providers={ProviderName.claude_cli: provider},
        clock=lambda: SUNDAY.astimezone(UTC),
    )


def test_the_weekly_job_caches_a_fresh_pool_and_keeps_board_lines_apart() -> None:
    repo = MemoryRepo(CONFIG)
    old_pool = {
        "persona": "coach",
        "trigger": "milestone",
        "milestone": "streak",
        "quest_id": None,
        "text": "old",
        "variant": 1,
        "condition": "any",
    }
    repo.lines = [dict(old_pool)]
    provider = ScriptedProvider({"ops": []}, full_pool())
    [d] = weekly(repo, provider).evaluate(Trigger.tick)
    assert d.status == Status.succeeded, d.reason

    pool = [line for line in repo.lines if line["trigger"] == "milestone"]
    assert len(pool) == len(SLUGS) * len(MILESTONES) * 2
    assert all(line["text"] != "old" for line in pool), "last week's pool is replaced"
    assert all(line["run_id"] for line in pool), "tied to the weekly run"
    assert "celebration lines" in provider.requests[1].system

    # daily_am replaces board lines every morning; it must leave the pool alone.
    repo.replace_board_lines([])
    assert len([line for line in repo.lines if line["trigger"] == "milestone"]) == len(pool)


def test_a_bad_pool_never_fails_the_weekly_plan() -> None:
    repo = MemoryRepo(CONFIG)
    bad = {"lines": [{"persona": "coach", "milestone": "streak", "variant": 1, "text": "Hi"}]}
    provider = ScriptedProvider({"ops": []}, bad, bad)  # invalid twice -> no provider left
    [d] = weekly(repo, provider).evaluate(Trigger.tick)
    assert d.status == Status.succeeded, d.reason
    assert not [line for line in repo.lines if line["trigger"] == "milestone"]


def test_pool_rules() -> None:
    assert check_pool(MilestonePool.model_validate(full_pool()), SLUGS, MILESTONES) == []

    partial = full_pool()
    partial["lines"] = [x for x in partial["lines"] if x["milestone"] != "perfect_week"]
    problems = check_pool(MilestonePool.model_validate(partial), SLUGS, MILESTONES)
    assert any("no lines for ['perfect_week']" in p for p in problems)

    leaky = MilestonePool.model_validate(full_pool("Call me at 300 555 1234 {milestone}"))
    assert any("personal data" in p for p in check_pool(leaky, SLUGS, MILESTONES))

    unknown = MilestonePool.model_validate(full_pool("{mood} {milestone}"))
    assert any("unknown placeholder" in p for p in check_pool(unknown, SLUGS, MILESTONES))
