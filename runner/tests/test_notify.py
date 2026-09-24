from __future__ import annotations

import base64
import json
import os
import sys
import threading
import uuid
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from runner.notify.push import Gone, generate_vapid_keys, payload, webpush_sender
from runner.notify.rules import in_quiet_hours, plan_notices, streak_days
from runner.notify.step import run_notifications
from runner.repo import MemoryRepo

sys.path.insert(0, str(Path(__file__).parent))
from test_engine import CONFIG, quest  # noqa: E402

BOGOTA = ZoneInfo("America/Bogota")


def at(h: int, m: int = 0, day: int = 25) -> datetime:
    return datetime(2026, 9, day, h, m, tzinfo=BOGOTA)


def kinds(notices) -> list[str]:
    return sorted(n.kind for n in notices)


def done_on(day: int) -> Any:
    return quest(
        status="done",
        scheduled_for=f"2026-09-{day:02d}",
        completed_at=at(9, day=day).astimezone(UTC).isoformat(),
    )


# -- rules --------------------------------------------------------------------------------


def test_day_ready_and_recap_follow_the_daily_jobs() -> None:
    qs = [quest(estimate_min=30), quest(estimate_min=15)]
    ready = plan_notices(CONFIG, qs, at(7), am_ready=True, pm_done=False)
    assert kinds(ready) == ["day_ready"]
    assert ready[0].body == "2 quests, about 45 min."
    assert ready[0].target == "questboard://today"
    assert ready[0].persona == "coach"
    assert kinds(plan_notices(CONFIG, qs, at(7), am_ready=False, pm_done=False)) == []
    recap = plan_notices(CONFIG, qs + [done_on(25)], at(21), am_ready=False, pm_done=True)
    assert [n.body for n in recap if n.kind == "day_recap"] == [
        "1 finished today; 2 carried to tomorrow."
    ]


def test_deadlines_make_due_and_overdue_notices_per_quest() -> None:
    soon = quest(deadline=at(9).astimezone(UTC).isoformat(), title="Pay rent")
    late = quest(deadline=at(6).astimezone(UTC).isoformat())
    later = quest(deadline=at(18).astimezone(UTC).isoformat())
    notices = plan_notices(CONFIG, [soon, late, later], at(7, 30), am_ready=False, pm_done=False)
    assert kinds(notices) == ["quest_due", "quest_overdue"]
    due = next(n for n in notices if n.kind == "quest_due")
    assert due.target == f"questboard://quest/{soon.id}" and due.body == "Pay rent"


def test_streak_risk_in_the_evening_only_when_nothing_is_finished_today() -> None:
    history = [done_on(22), done_on(23), done_on(24)]
    assert streak_days(history, at(19)) == 3
    evening = plan_notices(CONFIG, history, at(19, 30), am_ready=False, pm_done=False)
    assert [n.body for n in evening] == ["Finish one quest today to keep your 3-day streak."]
    assert plan_notices(CONFIG, history, at(15), am_ready=False, pm_done=False) == []
    saved = history + [done_on(25)]
    assert plan_notices(CONFIG, saved, at(19, 30), am_ready=False, pm_done=False) == []


def test_quiet_hours_wrap_midnight() -> None:
    assert in_quiet_hours(CONFIG, at(23)) and in_quiet_hours(CONFIG, at(6, 59))
    assert not in_quiet_hours(CONFIG, at(7))


# -- step ---------------------------------------------------------------------------------


CLOCK = [at(7)]


def step(repo: MemoryRepo, now: datetime, send):
    CLOCK[0] = now
    return run_notifications(repo, CONFIG, now, send)


def repo_with(qs, am_success: datetime | None = None) -> MemoryRepo:
    repo = MemoryRepo(CONFIG)
    repo.clock = lambda: CLOCK[0]
    repo.quests = qs
    if am_success:
        repo.state["last_am_success"] = am_success.isoformat()
    return repo


def test_step_dedups_waits_for_quiet_hours_and_marks_sent() -> None:
    repo = repo_with([quest()], am_success=at(5, 31))
    repo.push_subscriptions = [
        {"id": "s1", "endpoint": "https://push.example/1", "p256dh": "x", "auth": "y"}
    ]
    sent: list[bytes] = []

    def send(sub, body):
        sent.append(body)

    # 06:00 is inside quiet hours: recorded, not delivered.
    step(repo, at(6), send)
    assert len(repo.notifications) == 1 and repo.notifications[0]["sent_at"] is None
    assert sent == []
    # 07:05: delivered once; later ticks neither re-create nor re-send.
    result = step(repo, at(7, 5), send)
    step(repo, at(7, 10), send)
    assert result.sent == 1 and len(sent) == 1
    assert len(repo.notifications) == 1 and repo.notifications[0]["sent_at"] is not None
    assert json.loads(sent[0])["kind"] == "day_ready"


def test_step_removes_gone_endpoints_and_skips_stale_notices() -> None:
    repo = repo_with([quest()], am_success=at(5, 31))
    repo.push_subscriptions = [
        {"id": "gone", "endpoint": "https://push.example/g", "p256dh": "x", "auth": "y"},
        {"id": "ok", "endpoint": "https://push.example/o", "p256dh": "x", "auth": "y"},
    ]
    repo.notifications = [
        {
            "id": "old",
            "kind": "day_recap",
            "target": "questboard://today",
            "dedup_date": "2026-09-24",
            "channels": ["pc", "push"],
            "sent_at": None,
            "created_at": at(7) - timedelta(hours=20),
        }
    ]
    delivered: list[str] = []

    def send(sub, body):
        if sub["id"] == "gone":
            raise Gone()
        delivered.append(json.loads(body)["kind"])

    result = step(repo, at(8), send)
    assert delivered == ["day_ready"]  # the 20-hour-old recap is not pushed
    assert [s["id"] for s in repo.push_subscriptions] == ["ok"]
    assert (result.sent, result.removed) == (1, 1)


def test_step_without_push_configured_still_records_notifications() -> None:
    repo = repo_with([quest()], am_success=at(5, 31))
    step(repo, at(8), None)
    assert repo.notifications[0]["sent_at"] is not None  # PC reads rows over realtime


# -- real Web Push encryption against a local push "service" ---------------------------------


def test_webpush_encrypts_to_the_browser_key_and_signs_with_vapid() -> None:
    import http_ece
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    browser_key = ec.generate_private_key(ec.SECP256R1())
    auth_secret = os.urandom(16)
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()  # noqa: E731
    p256dh = b64(
        browser_key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    )
    received: dict[str, Any] = {}

    class Push(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            received["headers"] = dict(self.headers)
            received["body"] = self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(410 if self.path.endswith("/gone") else 201)
            self.end_headers()

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Push)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    private, _public = generate_vapid_keys()
    send = webpush_sender(private)
    note = {
        "kind": "quest_due",
        "title": "Due soon",
        "body": "Stretch",
        "target": "questboard://today",
    }
    old_proxy = {
        k: os.environ.pop(k, None)
        for k in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy")
    }
    try:
        send(
            {"endpoint": f"{base}/sub/{uuid.uuid4()}", "p256dh": p256dh, "auth": b64(auth_secret)},
            payload(note),
        )
        with pytest.raises(Gone):
            send(
                {"endpoint": f"{base}/gone", "p256dh": p256dh, "auth": b64(auth_secret)},
                payload(note),
            )
    finally:
        server.shutdown()
        os.environ.update({k: v for k, v in old_proxy.items() if v})

    headers = {k.lower(): v for k, v in received["headers"].items()}
    assert headers["content-encoding"] == "aes128gcm"
    assert headers["authorization"].startswith("vapid t=")
    plain = http_ece.decrypt(received["body"], private_key=browser_key, auth_secret=auth_secret)
    assert json.loads(plain) == {**note, "persona": None}
