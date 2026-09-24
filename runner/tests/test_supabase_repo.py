"""SupabaseRepo against a tiny in-memory PostgREST + auth stand-in."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from questboard_schema.common_schema import JobName, ProviderName
from questboard_schema.llm_run_schema import LLMRun, Status, TokenUsage, Trigger

from runner.repo import RepoUnavailable
from runner.supabase_repo import AuthError, MemoryTokenStore, SupabaseRepo

USER = "11111111-1111-4111-8111-111111111111"
CONFIG = json.loads(
    """{"timezone": "America/Bogota", "goals": [],
    "capacity": {"weekday_hours": 3, "weekend_hours": 5, "focus_factor": 0.7},
    "quiet_hours": {"start": "22:00", "end": "07:00"}, "xp_weights": {},
    "llm": {"providers": ["claude-cli"]}, "persona_order": ["coach"],
    "integrations": {"gmail": false, "gcal": false},
    "features": {"three_d": false, "mobile_rehydration": false},
    "notifications": {"persona_speech_per_day": 2, "persona_speech_on_mobile": false}}"""
)


def jwt(sub: str, n: int) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"sub": sub, "n": n}).encode()).rstrip(b"=")
    return f"h.{body.decode()}.s"


class FakeSupabase:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {
            "config": [{"user_id": USER, "data": CONFIG}],
            "runner_state": [
                {
                    "user_id": USER,
                    "heartbeat_at": None,
                    "last_am_success": None,
                    "last_pm_success": None,
                    "last_ingest_at": None,
                    "lock_holder": None,
                    "lock_acquired_at": None,
                    "provider_health": {},
                    "runner_version": None,
                    "updated_at": "2026-09-25T10:00:00+00:00",
                }
            ],
            "llm_runs": [],
        }
        self.issued = 0
        self.valid: set[str] = set()
        self.refresh = "r0"
        self.requests: list[httpx.Request] = []
        self.down = False

    def expire_access_tokens(self) -> None:
        self.valid.clear()

    def _session(self) -> httpx.Response:
        self.issued += 1
        access = jwt(USER, self.issued)
        self.valid.add(access)
        self.refresh = f"r{self.issued}"
        return httpx.Response(200, json={"access_token": access, "refresh_token": self.refresh})

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        if self.down:
            raise httpx.ConnectError("offline")
        path = req.url.path
        if path == "/auth/v1/token":
            body = json.loads(req.content)
            grant = req.url.params["grant_type"]
            if grant == "password" and body == {"email": "me@x.test", "password": "pw"}:
                return self._session()
            if grant == "refresh_token" and body["refresh_token"] == self.refresh:
                return self._session()
            return httpx.Response(400, json={"error": "invalid_grant"})
        assert req.headers["apikey"] == "anon"
        if req.headers.get("authorization", "").removeprefix("Bearer ") not in self.valid:
            return httpx.Response(401, json={"message": "JWT expired"})
        table = path.removeprefix("/rest/v1/")
        rows = self.tables[table]
        filters = {k: v for k, v in req.url.params.items() if k not in ("select", "order", "limit")}

        def match(row: dict[str, Any]) -> bool:
            for col, cond in filters.items():
                op, _, value = cond.partition(".")
                if op == "eq" and str(row.get(col)) != value:
                    return False
                if op == "is" and row.get(col) is not None:
                    return False
            return True

        if req.method == "GET":
            found = [r for r in rows if match(r)]
            if "order" in req.url.params:
                found.sort(key=lambda r: r[req.url.params["order"]])
            select = req.url.params.get("select", "*")
            if select != "*":
                found = [{c: r.get(c) for c in select.split(",")} for r in found]
            return httpx.Response(200, json=found)
        if req.method == "POST":
            row = {"id": str(uuid.uuid4()), "user_id": USER, **json.loads(req.content)}
            rows.append(row)
            return httpx.Response(201, json=[{k: v for k, v in row.items() if k != "user_id"}])
        if req.method == "PATCH":
            for r in rows:
                if match(r):
                    r.update(json.loads(req.content))
            return httpx.Response(204)
        return httpx.Response(405)


def make() -> tuple[SupabaseRepo, FakeSupabase, MemoryTokenStore]:
    fake = FakeSupabase()
    tokens = MemoryTokenStore()
    repo = SupabaseRepo(
        "https://proj.supabase.co",
        "anon",
        tokens,
        httpx.Client(transport=httpx.MockTransport(fake)),
    )
    repo.sign_in("me@x.test", "pw")
    return repo, fake, tokens


def test_sign_in_keeps_only_the_refresh_token_and_knows_the_user() -> None:
    repo, fake, tokens = make()
    assert tokens.token == fake.refresh
    assert repo.user_id == USER
    with pytest.raises(AuthError):
        SupabaseRepo("https://p", "anon", MemoryTokenStore(), repo.http).sign_in("me@x.test", "no")


def test_config_and_runner_state_round_trip() -> None:
    repo, fake, _ = make()
    repo.ping()
    assert repo.get_config().timezone == "America/Bogota"
    repo.update_runner_state({"heartbeat_at": datetime(2026, 9, 25, 11, tzinfo=UTC)})
    state = repo.get_runner_state()
    assert state is not None and state.heartbeat_at == datetime(2026, 9, 25, 11, tzinfo=UTC)
    patch = next(r for r in fake.requests if r.method == "PATCH")
    assert patch.url.params["user_id"] == f"eq.{USER}"


def test_llm_runs_map_token_columns_both_ways() -> None:
    repo, fake, _ = make()
    run = repo.insert_run(
        LLMRun(
            job=JobName.daily_am,
            slot="AM",
            date=date(2026, 9, 25),
            trigger=Trigger.tick,
            attempt=1,
            status=Status.running,
            started_at=datetime(2026, 9, 25, 10, 30, tzinfo=UTC),
        )
    )
    assert run.id is not None
    repo.update_run(
        str(run.id),
        {
            "status": Status.succeeded,
            "provider_used": ProviderName.claude_cli,
            "tokens": TokenUsage(input=120, output=30),
        },
    )
    stored = fake.tables["llm_runs"][0]
    assert (stored["tokens_input"], stored["tokens_output"]) == (120, 30)
    assert "tokens" not in stored
    [again] = repo.list_runs(JobName.daily_am, "AM", date(2026, 9, 25))
    assert again.tokens == TokenUsage(input=120, output=30)
    assert again.status == Status.succeeded
    assert repo.list_runs(JobName.weekly, None, date(2026, 9, 25)) == []
    get = [r for r in fake.requests if r.method == "GET" and "llm_runs" in r.url.path][-1]
    assert get.url.params["slot"] == "is.null"


def test_expired_access_token_is_refreshed_and_rotated() -> None:
    repo, fake, tokens = make()
    before = tokens.token
    fake.expire_access_tokens()
    repo.ping()
    assert tokens.token != before  # rotated refresh token saved


def test_offline_and_lost_session() -> None:
    repo, fake, tokens = make()
    fake.down = True
    with pytest.raises(RepoUnavailable):
        repo.ping()
    fake.down = False
    fake.expire_access_tokens()
    tokens.token = "revoked"
    with pytest.raises(AuthError):
        repo.ping()


def test_scheduler_runs_end_to_end_on_the_supabase_repo() -> None:
    from runner.scheduler.core import JobResult, Scheduler

    repo, fake, _ = make()
    sched = Scheduler(
        repo=repo,
        handlers={JobName.daily_am: lambda ctx: JobResult(ProviderName.claude_cli)},
        providers={},
        clock=lambda: datetime(2026, 9, 25, 11, 0, tzinfo=UTC),  # 06:00 in Bogota
    )
    sched.providers = {ProviderName.claude_cli: _Always()}
    [d] = sched.evaluate(Trigger.tick)
    assert d.status == Status.succeeded
    assert fake.tables["llm_runs"][0]["status"] == "succeeded"
    assert fake.tables["runner_state"][0]["heartbeat_at"] is not None


class _Always:
    name = ProviderName.claude_cli

    def is_available(self) -> bool:
        return True
