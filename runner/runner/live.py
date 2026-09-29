"""P1 live requests (pending_live_requests): answered between ticks, oldest first.

Requests wait while no provider is reachable (the app shows "pending"); after a day they are
cancelled. `replan` ("suggest quests now") runs a forced manual planning job through the
scheduler, so it is recorded in llm_runs and writes proposals only (invariant 3). Kinds without
a handler yet (quest_review, voice_fallback) fail with a clear reason instead of waiting forever.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from questboard_schema.common_schema import JobName
from questboard_schema.config_schema import Config
from questboard_schema.llm_run_schema import Status
from questboard_schema.replan_request_schema import ReplanRequest
from questboard_schema.replan_result_schema import ReplanResult

from runner.engine.packs import Pack, load_packs
from runner.engine.setup import setup_turn
from runner.providers.base import Provider, ProviderError
from runner.repo import Repo

MAX_AGE = timedelta(days=1)
PER_POLL = 3

Handler = Callable[[dict[str, Any], Config, list[Pack], list[Provider]], tuple[dict[str, Any], Any]]
HANDLERS: dict[str, Handler] = {"setup_assistant": setup_turn}
# (job) -> the scheduler's Decision for a forced manual run; see Scheduler.replan.
Replan = Callable[[JobName], Any]


def process_live(
    repo: Repo,
    config: Config,
    providers: list[Provider],
    now: datetime | None = None,
    packs: list[Pack] | None = None,
    replan: Replan | None = None,
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
        if req["kind"] == "replan" and replan is not None:
            if not available:
                break
            repo.update_request(req["id"], {"status": "running"})
            finished += _replan(repo, req, replan)
            continue
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


def _replan(repo: Repo, req: dict[str, Any], replan: Replan) -> int:
    """Forced planning run for a `replan` request. Failures and skips carry the scheduler's
    reason (never model text); the plan itself is in quest_proposals and on the llm_runs row."""
    try:
        job = JobName(ReplanRequest.model_validate(req["payload"]).job.value)
        decision = replan(job)
    except Exception as exc:  # noqa: BLE001 - class name only: messages may carry data
        repo.update_request(req["id"], {"status": "failed", "error": type(exc).__name__})
        return 0
    status = decision.status.value if decision.status else "skipped"
    result = ReplanResult(
        status=status, reason=decision.reason[:200], ops_count=decision.ops_count
    ).model_dump(mode="json")
    if decision.status == Status.succeeded:
        repo.update_request(req["id"], {"status": "done", "result": result})
        return 1
    fields = {"status": "failed", "error": decision.reason[:500], "result": result}
    repo.update_request(req["id"], fields)
    return 0
