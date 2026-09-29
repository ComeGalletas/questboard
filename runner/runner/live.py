"""P1 live requests (pending_live_requests): answered between ticks, oldest first.

Requests wait while no provider is reachable (the app shows "pending"); after a day they are
cancelled. `replan` ("suggest quests now") runs a forced manual planning job through the
scheduler, so it is recorded in llm_runs and writes proposals only (invariant 3). `notify_test`
is code only (no provider): it is answered first, even while LLM requests wait, by sending a
test Web Push (runner.notify.selftest). Kinds without a handler yet (quest_review,
voice_fallback) fail with a clear reason instead of waiting forever.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from questboard_schema.common_schema import JobName
from questboard_schema.config_schema import Config
from questboard_schema.llm_run_schema import Status
from questboard_schema.notify_test_request_schema import NotifyTestRequest
from questboard_schema.replan_request_schema import ReplanRequest
from questboard_schema.replan_result_schema import ReplanResult

from runner.engine.packs import Pack, load_packs
from runner.engine.setup import setup_turn
from runner.notify.push import Sender
from runner.notify.selftest import NotifyTestError, send_test
from runner.providers.base import Provider, ProviderError
from runner.repo import Repo, RepoUnavailable

MAX_AGE = timedelta(days=1)
PER_POLL = 3
CODE_ONLY = ("notify_test",)  # need no provider, so they never queue behind LLM requests

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
    push: Sender | None = None,
) -> int:
    """Answer up to PER_POLL pending requests; returns how many were finished."""
    now = now or datetime.now(UTC)
    finished = 0
    for req in repo.list_pending_requests(limit=PER_POLL, kinds=CODE_ONLY):
        if not _expired(repo, req, now):
            finished += _notify_test(repo, req, config, push)
    pending = repo.list_pending_requests(limit=PER_POLL)
    if not pending:
        return finished
    available = [p for p in providers if p.is_available()]
    for req in pending:
        if req["kind"] in CODE_ONLY or _expired(repo, req, now):
            continue  # a code-only one past this poll's batch goes out next poll
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


def _expired(repo: Repo, req: dict[str, Any], now: datetime) -> bool:
    created = req["created_at"]
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    if now - created > MAX_AGE:
        repo.update_request(req["id"], {"status": "cancelled", "error": "expired"})
        return True
    return False


def _notify_test(repo: Repo, req: dict[str, Any], config: Config, push: Sender | None) -> int:
    """Send the test push now. Done when it was attempted (per-device outcomes in the result);
    failed only when nothing could be sent (no VAPID key, no subscribed device)."""
    try:
        kind = NotifyTestRequest.model_validate(req["payload"]).kind
        result = send_test(repo, config, kind, push)
    except NotifyTestError as exc:
        repo.update_request(req["id"], {"status": "failed", "error": str(exc)[:500]})
        return 0
    except RepoUnavailable:
        raise  # stays pending; the next poll retries
    except Exception as exc:  # noqa: BLE001 - class name only: messages may carry data
        repo.update_request(req["id"], {"status": "failed", "error": type(exc).__name__})
        return 0
    repo.update_request(req["id"], {"status": "done", "result": result.model_dump(mode="json")})
    return 1


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
