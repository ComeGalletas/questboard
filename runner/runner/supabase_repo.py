"""Supabase (PostgREST) implementation of `Repo`, signed in as the single user.

The runner authenticates like any other client, so owner-only RLS applies to it too and no
service-role key lives on the PC. The rotating refresh token is kept in the OS keychain.
Error messages carry status codes only, never response bodies.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import httpx
from pydantic_core import to_jsonable_python
from questboard_schema.common_schema import JobName
from questboard_schema.config_schema import Config
from questboard_schema.llm_run_schema import LLMRun
from questboard_schema.quest_schema import Quest
from questboard_schema.runner_state_schema import RunnerState

from runner.repo import ACTIVE, RepoUnavailable

KEYRING_SERVICE = "questboard-runner"
KEYRING_USER = "supabase-refresh-token"
TIMEOUT = 15.0
RUN_COLUMNS = (
    "id,job,slot,date,trigger,provider_used,attempt,status,tokens_input,tokens_output,"
    "error,started_at,finished_at"
)


QUEST_COLUMNS = ",".join(Quest.model_fields)


class TokenStore(Protocol):
    def load(self) -> str | None: ...
    def save(self, token: str) -> None: ...


class KeyringTokenStore:
    """OS keychain (Windows Credential Manager, macOS Keychain, Secret Service)."""

    def load(self) -> str | None:
        import keyring

        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER)

    def save(self, token: str) -> None:
        import keyring

        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)


@dataclass
class MemoryTokenStore:
    token: str | None = None

    def load(self) -> str | None:
        return self.token

    def save(self, token: str) -> None:
        self.token = token


class AuthError(RepoUnavailable):
    """Sign-in failed or the stored session is gone; run `python -m runner login`."""


def _user_id(access_token: str) -> str:
    payload = access_token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


def _jsonable(value: Any) -> Any:
    return to_jsonable_python(value, by_alias=True)


class SupabaseRepo:
    def __init__(
        self,
        url: str,
        anon_key: str,
        tokens: TokenStore,
        client: httpx.Client | None = None,
    ):
        self.url = url.rstrip("/")
        self.anon_key = anon_key
        self.tokens = tokens
        self.http = client or httpx.Client(timeout=TIMEOUT)
        self._access: str | None = None

    # -- auth -------------------------------------------------------------------------------

    def sign_in(self, email: str, password: str) -> None:
        """One-time setup: exchange the password for a session; only the refresh token is kept."""
        self._token_request("password", {"email": email, "password": password})

    def _refresh(self) -> None:
        refresh = self.tokens.load()
        if not refresh:
            raise AuthError("no stored session; run `python -m runner login`")
        self._token_request("refresh_token", {"refresh_token": refresh})

    def _token_request(self, grant: str, body: dict[str, str]) -> None:
        try:
            resp = self.http.post(
                f"{self.url}/auth/v1/token",
                params={"grant_type": grant},
                headers={"apikey": self.anon_key},
                json=body,
            )
        except httpx.HTTPError:
            raise RepoUnavailable("auth endpoint unreachable") from None
        if resp.status_code in (400, 401, 403):
            raise AuthError(f"sign-in rejected ({resp.status_code})")
        if resp.status_code != 200:
            raise RepoUnavailable(f"auth returned {resp.status_code}")
        session = resp.json()
        self._access = session["access_token"]
        self.tokens.save(session["refresh_token"])  # Supabase rotates refresh tokens

    @property
    def user_id(self) -> str:
        if self._access is None:
            self._refresh()
        assert self._access is not None
        return _user_id(self._access)

    # -- http -------------------------------------------------------------------------------

    def _request(
        self,
        method: str,
        table: str,
        params: dict[str, str] | None = None,
        body: Any = None,
        prefer: str | None = None,
    ) -> Any:
        if self._access is None:
            self._refresh()
        for attempt in (1, 2):
            headers = {"apikey": self.anon_key, "Authorization": f"Bearer {self._access}"}
            if prefer:
                headers["Prefer"] = prefer
            try:
                resp = self.http.request(
                    method,
                    f"{self.url}/rest/v1/{table}",
                    params=params,
                    headers=headers,
                    json=_jsonable(body) if body is not None else None,
                )
            except httpx.HTTPError:
                raise RepoUnavailable(f"{table}: network error") from None
            if resp.status_code == 401 and attempt == 1:
                self._refresh()  # access token expired
                continue
            if resp.status_code >= 500 or resp.status_code in (401, 403):
                raise RepoUnavailable(f"{table}: {resp.status_code}")
            if resp.status_code >= 400:
                raise RuntimeError(f"{table}: request rejected ({resp.status_code})")
            return resp.json() if resp.content else None
        raise RepoUnavailable(f"{table}: unauthorized")

    # -- Repo -------------------------------------------------------------------------------

    def ping(self) -> None:
        self._request("GET", "runner_state", {"select": "user_id", "limit": "1"})

    def get_config(self) -> Config:
        rows = self._request("GET", "config", {"select": "data"})
        if not rows:
            raise RuntimeError("config row missing")
        return Config.model_validate(rows[0]["data"])

    def get_runner_state(self) -> RunnerState | None:
        rows = self._request("GET", "runner_state", {"select": "*"})
        return RunnerState.model_validate(rows[0]) if rows else None

    def update_runner_state(self, fields: dict[str, Any]) -> None:
        self._request(
            "PATCH", "runner_state", {"user_id": f"eq.{self.user_id}"}, fields, "return=minimal"
        )

    def list_runs(self, job: JobName, slot: str | None, day: date) -> list[LLMRun]:
        params = {
            "select": RUN_COLUMNS,
            "job": f"eq.{job.value}",
            "date": f"eq.{day.isoformat()}",
            "slot": f"eq.{slot}" if slot else "is.null",
            "order": "attempt",
        }
        return [_run_from_row(r) for r in self._request("GET", "llm_runs", params)]

    def insert_run(self, run: LLMRun) -> LLMRun:
        row = _run_to_row(run.model_dump(exclude_none=True, exclude={"id"}))
        [stored] = self._request(
            "POST", "llm_runs", {"select": RUN_COLUMNS}, row, "return=representation"
        )
        return _run_from_row(stored)

    def update_run(self, run_id: str, fields: dict[str, Any]) -> None:
        self._request(
            "PATCH", "llm_runs", {"id": f"eq.{run_id}"}, _run_to_row(fields), "return=minimal"
        )

    def list_quests(self, since: date) -> list[Quest]:
        active = ",".join(ACTIVE)
        params = {
            "select": QUEST_COLUMNS,
            "or": f"(status.in.({active}),scheduled_for.gte.{since.isoformat()})",
            "order": "created_at",
        }
        return [Quest.model_validate(r) for r in self._request("GET", "quests", params)]

    def update_quest(self, quest_id: str, fields: dict[str, Any]) -> None:
        self._request("PATCH", "quests", {"id": f"eq.{quest_id}"}, fields, "return=minimal")

    def list_feedback(self, since: date) -> list[dict[str, Any]]:
        params = {
            "select": "quest_id,action,comment,created_at",
            "created_at": f"gte.{since.isoformat()}",
        }
        return self._request("GET", "quest_feedback", params)

    def supersede_pending_proposals(self) -> int:
        rows = self._request(
            "PATCH",
            "quest_proposals",
            {"status": "eq.pending", "select": "id"},
            {"status": "superseded"},
            "return=representation",
        )
        return len(rows or [])

    def insert_proposals(self, rows: list[dict[str, Any]]) -> None:
        if rows:
            self._request("POST", "quest_proposals", None, rows, "return=minimal")

    def replace_quest_lines(self, quest_ids: list[str], rows: list[dict[str, Any]]) -> None:
        if quest_ids:
            params = {"quest_id": f"in.({','.join(quest_ids)})", "used_at": "is.null"}
            self._request("DELETE", "persona_lines", params, None, "return=minimal")
        if rows:
            self._request("POST", "persona_lines", None, rows, "return=minimal")

    def replace_board_lines(self, rows: list[dict[str, Any]]) -> None:
        params = {"quest_id": "is.null", "used_at": "is.null"}
        self._request("DELETE", "persona_lines", params, None, "return=minimal")
        if rows:
            self._request("POST", "persona_lines", None, rows, "return=minimal")


def _run_to_row(fields: dict[str, Any]) -> dict[str, Any]:
    row = dict(fields)
    if "tokens" in row:
        tokens = row.pop("tokens")
        if tokens is not None:
            t = tokens if isinstance(tokens, dict) else tokens.model_dump()
            row["tokens_input"], row["tokens_output"] = t["input"], t["output"]
    return row


def _run_from_row(row: dict[str, Any]) -> LLMRun:
    data = dict(row)
    ti, to = data.pop("tokens_input", None), data.pop("tokens_output", None)
    data["tokens"] = {"input": ti, "output": to} if ti is not None and to is not None else None
    return LLMRun.model_validate(data)
