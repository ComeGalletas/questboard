"""Runner against a real Supabase stack (local `supabase start` or a hosted project).

Skipped unless these are set:
  QUESTBOARD_IT_URL, QUESTBOARD_IT_ANON_KEY, QUESTBOARD_IT_EMAIL, QUESTBOARD_IT_PASSWORD
Uses a scripted provider, so no model is called. Leaves the DB with extra rows; run against a
disposable stack (`pnpm db:reset` restores it).
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.llm_run_schema import Status, Trigger

from runner.engine.daily import daily_am, daily_pm
from runner.engine.packs import load_packs
from runner.scheduler.core import Scheduler
from runner.supabase_repo import MemoryTokenStore, SupabaseRepo

ENV = (
    "QUESTBOARD_IT_URL",
    "QUESTBOARD_IT_ANON_KEY",
    "QUESTBOARD_IT_EMAIL",
    "QUESTBOARD_IT_PASSWORD",
)
pytestmark = pytest.mark.skipif(
    not all(os.environ.get(k) for k in ENV), reason="live Supabase not configured"
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_engine import ADD_RUN, ScriptedProvider, board, lines  # noqa: E402

BOGOTA = ZoneInfo("America/Bogota")


@pytest.fixture(scope="module")
def repo() -> SupabaseRepo:
    r = SupabaseRepo(
        os.environ["QUESTBOARD_IT_URL"],
        os.environ["QUESTBOARD_IT_ANON_KEY"],
        MemoryTokenStore(),
        httpx.Client(timeout=15, trust_env=False),  # local stack: bypass the HTTPS proxy
    )
    r.sign_in(os.environ["QUESTBOARD_IT_EMAIL"], os.environ["QUESTBOARD_IT_PASSWORD"])
    return r


def rest(repo: SupabaseRepo, method: str, table: str, **kw) -> httpx.Response:
    return repo.http.request(
        method,
        f"{repo.url}/rest/v1/{table}",
        headers={
            "apikey": repo.anon_key,
            "Authorization": f"Bearer {repo._access}",
            "Prefer": "return=representation",
        },
        **kw,
    )


def test_anonymous_clients_see_nothing(repo: SupabaseRepo) -> None:
    resp = repo.http.get(
        f"{repo.url}/rest/v1/quests",
        headers={"apikey": repo.anon_key, "Authorization": f"Bearer {repo.anon_key}"},
    )
    assert resp.status_code in (401, 403) or resp.json() == []


def test_config_state_and_heartbeat(repo: SupabaseRepo) -> None:
    repo.ping()
    assert repo.get_config().timezone
    stamp = datetime.now(UTC).replace(microsecond=0)
    repo.update_runner_state({"heartbeat_at": stamp})
    state = repo.get_runner_state()
    assert state is not None and state.heartbeat_at == stamp


@pytest.fixture
def clean_quests(repo: SupabaseRepo):
    """Leftover test quests would count as carried-over quests on a later run's board."""

    def wipe() -> None:
        rest(repo, "DELETE", "quests", params={"title": "eq.Integration stretch"})
        rest(repo, "DELETE", "quests", params={"source": "eq.llm", "title": "eq.Easy 3 km run"})
        rest(
            repo,
            "PATCH",
            "quest_proposals",
            params={"status": "eq.pending"},
            json={"status": "superseded"},
        )

    wipe()
    yield
    wipe()


def test_daily_am_then_pm_through_rls(repo: SupabaseRepo, clean_quests) -> None:
    # A fresh day far from real data so reruns don't collide with earlier runs.
    day = datetime(2031, 1, 6 + uuid.uuid4().int % 20, 6, 0, tzinfo=BOGOTA)
    # Idempotency is per (job, slot, date): forget earlier runs of this day on a reused DB.
    rest(repo, "DELETE", "llm_runs", params={"date": f"eq.{day.date().isoformat()}"})
    created = rest(
        repo,
        "POST",
        "quests",
        json={
            "title": "Integration stretch",
            "persona": "coach",
            "cadence": "daily",
            "category": "health",
            "estimate_min": 20,
            "priority": 2,
            "xp": 20,
            "source": "manual",
            "scheduled_for": day.date().isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    qid = created.json()[0]["id"]

    output = {
        "diff": {
            "ops": [
                {**ADD_RUN, "quest": {**ADD_RUN["quest"], "scheduled_for": day.date().isoformat()}}
            ]
        },
        "quest_lines": [
            {"quest": qid, "persona": "coach", "lines": lines("coach")},
            {"quest": "new:0", "persona": "coach", "lines": lines("coach")},
        ],
        "board_lines": board(),
    }
    # Only quests on the test day are in play: hide other open quests from the check by
    # keeping capacity generous for the weekday.
    sched = Scheduler(
        repo=repo,
        handlers={
            JobName.daily_am: lambda ctx: daily_am(ctx, load_packs()),
            JobName.daily_pm: daily_pm,
        },
        providers={ProviderName.claude_cli: ScriptedProvider(output, output)},
        clock=lambda: day.astimezone(UTC),
    )
    [am] = sched.evaluate(Trigger.manual, only=JobName.daily_am)
    assert am.status == Status.succeeded, am.reason

    proposals = rest(
        repo, "GET", "quest_proposals", params={"status": "eq.pending", "select": "op,lines,run_id"}
    ).json()
    assert [p["op"] for p in proposals] == ["add"]
    assert len(proposals[0]["lines"]) == 36
    cached = rest(
        repo, "GET", "persona_lines", params={"quest_id": f"eq.{qid}", "select": "trigger"}
    ).json()
    assert len(cached) == 36
    # The quest itself is untouched by daily_am (invariant 3).
    assert rest(repo, "GET", "quests", params={"id": f"eq.{qid}"}).json()[0]["carries"] == 0

    evening = day.replace(hour=21)
    sched.clock = lambda: evening.astimezone(UTC)
    [pm] = sched.evaluate(Trigger.manual, only=JobName.daily_pm)
    assert pm.status == Status.succeeded, pm.reason
    moved = rest(repo, "GET", "quests", params={"id": f"eq.{qid}"}).json()[0]
    assert moved["carries"] == 1
    assert moved["scheduled_for"] == (day.date() + timedelta(days=1)).isoformat()

    runs = repo.list_runs(JobName.daily_am, "AM", day.date())
    assert runs[-1].status == Status.succeeded
    print(json.dumps({"am_run": str(runs[-1].id), "quest": qid}))


def test_notifications_dedup_and_push_subscriptions(repo: SupabaseRepo) -> None:
    from runner.notify.step import run_notifications

    now = datetime.now(BOGOTA).replace(hour=12)  # outside default quiet hours
    target = f"questboard://quest/{uuid.uuid4()}"
    row = {
        "kind": "quest_due",
        "target": target,
        "persona": "coach",
        "title": "Due soon",
        "body": "Integration",
        "channels": ["pc", "push"],
        "dedup_date": now.date().isoformat(),
    }
    repo.insert_notifications([row])
    repo.insert_notifications([row])  # same (kind, target, date): ignored, not an error
    found = rest(repo, "GET", "notifications", params={"target": f"eq.{target}"}).json()
    assert len(found) == 1

    sub = rest(
        repo,
        "POST",
        "push_subscriptions",
        json={"endpoint": f"https://push.example/{uuid.uuid4()}", "p256dh": "k", "auth": "a"},
    )
    assert sub.status_code == 201, sub.text
    sent: list[str] = []
    run_notifications(repo, repo.get_config(), now, lambda s, body: sent.append(s["endpoint"]))
    assert sub.json()[0]["endpoint"] in sent
    after = rest(repo, "GET", "notifications", params={"target": f"eq.{target}"}).json()
    assert after[0]["sent_at"] is not None
