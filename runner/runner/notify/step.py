"""The per-tick notification step: plan -> insert (DB dedups) -> deliver outside quiet hours."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from questboard_schema.config_schema import Config

from runner.notify.push import Gone, PushResult, Sender, payload
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
    sent = removed = failed = 0
    gone: set[str] = set()
    for n in pending:
        if "push" not in n.get("channels", []):
            continue
        for sub in subs:
            if sub["id"] in gone:
                continue
            try:
                send(sub, payload(n))  # type: ignore[misc]
                sent += 1
            except Gone:
                gone.add(sub["id"])
                repo.delete_push_subscription(sub["id"])
                removed += 1
            except Exception:  # noqa: BLE001 - one bad endpoint must not block the rest
                failed += 1
    # Dispatched to every remote channel we have; the PC reads rows over realtime.
    repo.mark_notifications_sent([n["id"] for n in pending], datetime.now(UTC))
    return PushResult(sent, removed, failed)
