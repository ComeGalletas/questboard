"""The per-tick notification step: plan -> insert (DB dedups) -> deliver outside quiet hours."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from questboard_schema.config_schema import Config

from runner.notify.push import PushResult, Sender, payload, push_all
from runner.notify.rules import deliverable, plan_notices
from runner.repo import Repo

MAX_AGE = timedelta(hours=12)  # don't wake the phone with yesterday's news after an outage
HISTORY_DAYS = 14


def run_notifications(repo: Repo, config: Config, now: datetime, send: Sender | None) -> PushResult:
    state = repo.get_runner_state()
    today = now.date()

    def same_day(ts) -> bool:
        return ts is not None and ts.astimezone(now.tzinfo).date() == today

    quests = repo.list_quests(since=today - timedelta(days=HISTORY_DAYS))
    notices = plan_notices(
        config,
        quests,
        now,
        am_ready=bool(state and same_day(state.last_am_success)),
        pm_done=bool(state and same_day(state.last_pm_success)),
    )
    repo.insert_notifications([n.row(today) for n in notices])

    if not deliverable(config, now):
        return PushResult()
    pending = repo.list_undelivered_notifications(since=now - MAX_AGE)
    if not pending:
        return PushResult()
    subs = repo.list_push_subscriptions() if send else []
    outcomes: list[str] = []
    gone: set[str] = set()
    for n in pending:
        if send is None or "push" not in n.get("channels", []):
            continue
        outcomes += [d.outcome for d in push_all(repo, subs, send, payload(n), gone)]
    sent, removed, failed = (outcomes.count(k) for k in ("sent", "removed", "failed"))
    # Dispatched to every remote channel we have; the PC reads rows over realtime.
    repo.mark_notifications_sent([n["id"] for n in pending], datetime.now(UTC))
    return PushResult(sent, removed, failed)
