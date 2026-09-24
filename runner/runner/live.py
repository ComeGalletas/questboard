"""P1 live requests (pending_live_requests): answered between ticks, oldest first.

Requests wait while no provider is reachable (the app shows "pending"); after a day they are
cancelled. Kinds without a handler yet (replan, quest_review, voice_fallback) fail with a
clear reason instead of waiting forever.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from questboard_schema.config_schema import Config

from runner.engine.packs import Pack, load_packs
from runner.engine.setup import setup_turn
from runner.providers.base import Provider, ProviderError
from runner.repo import Repo

MAX_AGE = timedelta(days=1)
PER_POLL = 3

Handler = Callable[[dict[str, Any], Config, list[Pack], list[Provider]], tuple[dict[str, Any], Any]]
HANDLERS: dict[str, Handler] = {"setup_assistant": setup_turn}


def process_live(
    repo: Repo,
    config: Config,
    providers: list[Provider],
    now: datetime | None = None,
    packs: list[Pack] | None = None,
) -> int:
    """Answer up to PER_POLL pending requests; returns how many were finished."""
    now = now or datetime.now(UTC)
    pending = repo.list_pending_requests(limit=PER_POLL)
    if not pending:
        return 0
    available = [p for p in providers if p.is_available()]
    finished = 0
    for req in pending:
        created = req["created_at"]
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        if now - created > MAX_AGE:
            repo.update_request(req["id"], {"status": "cancelled", "error": "expired"})
            continue
        handler = HANDLERS.get(req["kind"])
        if handler is None:
            repo.update_request(
                req["id"], {"status": "failed", "error": f"{req['kind']} is not supported yet"}
            )
            continue
        if not available:
            break  # stays pending; P1 waits for a provider
        repo.update_request(req["id"], {"status": "running"})
        try:
            result, _ = handler(req["payload"], config, packs or load_packs(), available)
        except ProviderError as exc:
            repo.update_request(req["id"], {"status": "failed", "error": str(exc)[:500]})
        except Exception as exc:  # noqa: BLE001 - class name only: messages may carry data
            repo.update_request(req["id"], {"status": "failed", "error": type(exc).__name__})
        else:
            repo.update_request(req["id"], {"status": "done", "result": result})
            finished += 1
    return finished
