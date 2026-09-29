"""On-demand test notifications: `python -m runner notify-test [kind]`, or the app's
"Send test notification" (a `notify_test` live request answered by the runner, which holds the
VAPID private key).

A real Web Push goes out right away to every push_subscriptions row, bypassing quiet hours,
dedup and the 12 h max age. Nothing is written to `notifications`, so real dedup is untouched.
The payload is marked `test: true` with a "[Test]" title prefix, and carries a real deep link
for its kind so the tap-through can be tested too. Results name devices by user agent and a
short row id; endpoints and keys are never printed or stored.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from questboard_schema.common_schema import NotificationKind as Kind
from questboard_schema.config_schema import Config
from questboard_schema.notify_test_result_schema import NotifyTestResult
from questboard_schema.quest_schema import Quest

from runner.notify.push import Sender, payload, push_all
from runner.notify.rules import ACTIVE, TITLE_MAX
from runner.repo import Repo

TITLE_PREFIX = "[Test] "
TITLES: dict[Kind, str] = {
    Kind.day_ready: "Today's quests are ready",
    Kind.day_recap: "Day recap",
    Kind.week_ready: "This week's plan is ready",
    Kind.month_ready: "This month's plan is ready",
    Kind.quest_due: "Due soon",
    Kind.quest_overdue: "Overdue",
    Kind.capacity_alert: "Over capacity",
    Kind.streak_risk: "Streak at risk",
    Kind.persona_speech: "A word from your party",
    Kind.runner_stale: "Runner offline",
    Kind.live_pending: "Waiting for your PC",
}
QUEST_KINDS = {Kind.quest_due, Kind.quest_overdue}
TARGETS = {Kind.week_ready: "questboard://week", Kind.month_ready: "questboard://month"}
TODAY = "questboard://today"

# First match wins; the iOS home-screen app's user agent has no browser token.
PLATFORMS = {
    "iPhone": "iPhone",
    "iPad": "iPad",
    "Android": "Android",
    "Windows": "Windows",
    "Macintosh": "Mac",
    "Linux": "Linux",
}
BROWSERS = {
    "Edg": "Edge",
    "Firefox": "Firefox",
    "FxiOS": "Firefox",
    "CriOS": "Chrome",
    "Chrome": "Chrome",
    "Safari": "Safari",
}


class NotifyTestError(Exception):
    """Nothing could be sent (no VAPID key on this PC, or no subscribed device)."""


def device_label(sub: dict[str, Any]) -> str:
    ua = sub.get("user_agent") or ""
    platform = next((name for key, name in PLATFORMS.items() if key in ua), "Unknown device")
    browser = next((name for key, name in BROWSERS.items() if key in ua), "web app")
    return f"{platform}, {browser} ({str(sub['id'])[:8]})"


def _quest_for(kind: Kind, quests: list[Quest]) -> Quest | None:
    """An open quest to deep-link to: soonest deadline first, else the oldest open one."""
    if kind not in QUEST_KINDS:
        return None
    active = [q for q in quests if q.status.value in ACTIVE]
    with_deadline = sorted((q for q in active if q.deadline), key=lambda q: q.deadline)
    candidates = with_deadline or active
    return candidates[0] if candidates else None


def notice_for(kind: Kind, config: Config, quests: list[Quest]) -> dict[str, Any]:
    """The test notification's fields (the shape push.payload reads), never stored."""
    quest = _quest_for(kind, quests)
    order = [p.root for p in config.persona_order]
    persona = quest.persona.root if quest else (order[0] if order else None)
    if quest:
        target, body = f"questboard://quest/{quest.id}", f"Test for: {quest.title}"
    else:
        target = TARGETS.get(kind, TODAY)
        body = f"Test notification ({kind.value}). Tap to check the link opens the right screen."
    return {
        "kind": kind.value,
        "target": target,
        "persona": persona,
        "title": (TITLE_PREFIX + TITLES[kind])[:TITLE_MAX],
        "body": body[:280],
        "test": True,
    }


def send_test(repo: Repo, config: Config, kind: Kind, send: Sender | None) -> NotifyTestResult:
    if send is None:
        raise NotifyTestError(
            "QUESTBOARD_VAPID_PRIVATE_KEY is not set on the runner PC"
            " (see `python -m runner vapid`)"
        )
    subs = repo.list_push_subscriptions()
    if not subs:
        raise NotifyTestError(
            'No device has notifications on; tap "Enable notifications on this device" first'
        )
    today = datetime.now(ZoneInfo(config.timezone)).date()
    notice = notice_for(kind, config, repo.list_quests(since=today))
    by_id = {s["id"]: s for s in subs}
    deliveries = push_all(repo, subs, send, payload(notice), set())
    return NotifyTestResult.model_validate(
        {
            "kind": kind,
            "target": notice["target"],
            "devices": [
                {"device": device_label(by_id[d.sub_id]), "outcome": d.outcome, "error": d.error}
                for d in deliveries
            ],
        }
    )
