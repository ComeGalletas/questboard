from __future__ import annotations

import json
import sys
from datetime import UTC, date
from pathlib import Path

from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.llm_run_schema import Trigger

from runner.engine.calibration import calibration
from runner.engine.daily import daily_am
from runner.repo import MemoryRepo
from runner.scheduler.core import Scheduler

sys.path.insert(0, str(Path(__file__).parent))
from test_engine import (  # noqa: E402
    CONFIG,
    NOW,
    PACKS,
    TODAY,
    ScriptedProvider,
    lines,
    plan,
    quest,
)


def finished(category: str, estimate: int, actual: int, day: str = "2026-09-20", **over):
    return quest(
        category=category,
        estimate_min=estimate,
        actual_min=actual,
        status="done",
        scheduled_for=day,
        completed_at=f"{day}T15:00:00Z",
        **over,
    )


def test_median_ratio_per_category_with_minimum_samples_and_clamp() -> None:
    qs = [
        finished("learning", 30, 45),
        finished("learning", 60, 90),
        finished("learning", 20, 60),  # outlier: median ignores it
        finished("health", 30, 30),
        finished("health", 30, 30),  # only 2 samples: not reported
        finished("general", 10, 100),
        finished("general", 10, 90),
        finished("general", 10, 80),  # 8-10x: clamped to 3
        finished("learning", 30, 300, day="2026-08-01"),  # outside 30 days
        quest(category="learning", estimate_min=30),  # not finished
    ]
    assert calibration(qs, date(2026, 9, 25)) == {
        "general": {"ratio": 3.0, "samples": 3},
        "learning": {"ratio": 1.5, "samples": 3},
    }


def test_daily_am_prompt_carries_the_calibration() -> None:
    open_q = quest()
    repo = MemoryRepo(CONFIG)
    repo.quests = [open_q] + [
        finished("learning", 30, 45, day=f"2026-09-{d}") for d in (10, 12, 14)
    ]
    provider = ScriptedProvider(
        plan([], [{"quest": str(open_q.id), "persona": "coach", "lines": lines("coach")}])
    )
    Scheduler(
        repo=repo,
        handlers={JobName.daily_am: lambda c: daily_am(c, PACKS)},
        providers={ProviderName.claude_cli: provider},
        clock=lambda: NOW.astimezone(UTC),
    ).evaluate(Trigger.tick)
    context = json.loads(provider.requests[0].prompt.split("\n\n", 1)[1])
    assert context["estimate_calibration"] == {"learning": {"ratio": 1.5, "samples": 3}}
    assert "estimate_calibration" in provider.requests[0].system
    assert TODAY.isoformat() == context["today"]
