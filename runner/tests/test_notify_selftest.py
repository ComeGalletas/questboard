"""On-demand test notifications: `runner notify-test` and the `notify_test` live request."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from questboard_schema.common_schema import NotificationKind as Kind

import runner.__main__ as cli
from runner.live import process_live
from runner.notify.push import Gone
from runner.notify.selftest import NotifyTestError, device_label, send_test
from runner.repo import MemoryRepo

sys.path.insert(0, str(Path(__file__).parent))
from test_engine import CONFIG, PACKS, ScriptedProvider, quest  # noqa: E402

IPHONE_APP = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148"
)
WINDOWS_EDGE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
)
SUBS = [
    {
        "id": "a1b2c3d4-0000-4000-8000-000000000001",
        "endpoint": "https://web.push.apple.com/SECRET-ENDPOINT",
        "p256dh": "SECRET-P256DH",
        "auth": "SECRET-AUTH",
        "user_agent": IPHONE_APP,
    },
    {
        "id": "e5f6a7b8-0000-4000-8000-000000000002",
        "endpoint": "https://wns.example/GONE-ENDPOINT",
        "p256dh": "k",
        "auth": "a",
        "user_agent": WINDOWS_EDGE,
    },
    {
        "id": "c9d0e1f2-0000-4000-8000-000000000003",
        "endpoint": "https://fcm.example/BROKEN-ENDPOINT",
        "p256dh": "k",
        "auth": "a",
        "user_agent": None,
    },
]


class FakePush:
    """Records payloads; the second device is gone, the third fails."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def __call__(self, sub, data: bytes) -> None:
        if "GONE" in sub["endpoint"]:
            raise Gone()
        if "BROKEN" in sub["endpoint"]:
            raise RuntimeError("push failed (403)")
        self.sent.append(json.loads(data))


def repo_with_subs(quests=()) -> MemoryRepo:
    repo = MemoryRepo(CONFIG)
    repo.push_subscriptions = [dict(s) for s in SUBS]
    repo.quests = list(quests)
    return repo


def test_device_labels_come_from_the_user_agent_never_the_endpoint() -> None:
    assert device_label(SUBS[0]) == "iPhone, web app (a1b2c3d4)"
    assert device_label(SUBS[1]) == "Windows, Edge (e5f6a7b8)"
    assert device_label(SUBS[2]) == "Unknown device, web app (c9d0e1f2)"


def test_sends_to_every_device_now_and_cleans_up_dead_endpoints() -> None:
    repo = repo_with_subs()
    push = FakePush()
    result = send_test(repo, CONFIG, Kind.day_ready, push)
    assert [(d.device[:7], d.outcome.value, d.error) for d in result.devices] == [
        ("iPhone,", "sent", None),
        ("Windows", "removed", None),
        ("Unknown", "failed", "push failed (403)"),
    ]
    assert [s["id"] for s in repo.push_subscriptions] == [SUBS[0]["id"], SUBS[2]["id"]]
    (body,) = push.sent
    assert body["test"] is True and body["title"] == "[Test] Today's quests are ready"
    assert (body["kind"], body["target"], body["persona"]) == ("day_ready", result.target, "coach")
    assert result.target == "questboard://today"
    assert repo.notifications == []  # never a real row: real dedup stays untouched


@pytest.mark.parametrize(
    ("kind", "target"),
    [
        (Kind.week_ready, "questboard://week"),
        (Kind.month_ready, "questboard://month"),
        (Kind.streak_risk, "questboard://today"),
        (Kind.quest_due, "questboard://today"),  # no open quest to point at
    ],
)
def test_each_kind_gets_a_real_deep_link(kind: Kind, target: str) -> None:
    push = FakePush()
    assert send_test(repo_with_subs(), CONFIG, kind, push).target == target
    assert push.sent[0]["kind"] == kind.value


def test_quest_kinds_link_to_the_most_urgent_open_quest() -> None:
    soon = quest(title="Pay rent", persona="quartermaster", deadline="2026-09-30T12:00:00Z")
    later = quest(title="Call mom", deadline="2026-10-05T12:00:00Z")
    repo = repo_with_subs([later, quest(status="done"), soon])
    push = FakePush()
    result = send_test(repo, CONFIG, Kind.quest_overdue, push)
    assert result.target == f"questboard://quest/{soon.id}"
    assert push.sent[0]["persona"] == "quartermaster"
    assert push.sent[0]["body"] == "Test for: Pay rent"


def test_nothing_to_send_is_an_error() -> None:
    with pytest.raises(NotifyTestError, match="VAPID"):
        send_test(repo_with_subs(), CONFIG, Kind.day_ready, None)
    with pytest.raises(NotifyTestError, match="Enable notifications"):
        send_test(MemoryRepo(CONFIG), CONFIG, Kind.day_ready, FakePush())


def test_real_notifications_keep_their_payload_shape() -> None:
    from runner.notify.push import payload

    real = {"kind": "day_ready", "target": "questboard://today", "title": "T", "body": "B"}
    assert "test" not in json.loads(payload(real))


# -- CLI ----------------------------------------------------------------------------------


def test_cli_prints_per_device_results_without_endpoints_or_keys(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "sender_from_env", FakePush)
    assert cli.notify_test("week_ready", repo_with_subs()) == 0
    out = capsys.readouterr().out
    assert out.splitlines() == [
        "test week_ready -> questboard://week",
        "  iPhone, web app (a1b2c3d4): sent",
        "  Windows, Edge (e5f6a7b8): expired endpoint removed",
        "  Unknown device, web app (c9d0e1f2): failed (push failed (403))",
    ]
    assert "SECRET" not in out and "ENDPOINT" not in out


def test_cli_fails_clearly_without_a_vapid_key(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "sender_from_env", lambda: None)
    assert cli.notify_test("day_ready", repo_with_subs()) == 1
    assert "QUESTBOARD_VAPID_PRIVATE_KEY" in capsys.readouterr().err


def test_cli_rejects_unknown_kinds(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.main(["notify-test", "fireworks"])


# -- live request (the app's "Send test notification") ------------------------------------

NOW = datetime(2026, 9, 25, 15, 0, tzinfo=UTC)


def live(id: str, kind: str = "notify_test", **over):
    return {
        "id": id,
        "kind": kind,
        "status": "pending",
        "created_at": NOW - timedelta(seconds=5),
        "payload": {"kind": "day_ready"},
        **over,
    }


class Down(ScriptedProvider):
    def is_available(self) -> bool:
        return False


def test_live_request_is_answered_without_a_provider_and_ahead_of_llm_work() -> None:
    repo = repo_with_subs()
    setup = {"messages": [{"role": "user", "content": "hi"}]}
    repo.requests = [
        live(f"llm{i}", "setup_assistant", payload=setup, created_at=NOW - timedelta(minutes=i))
        for i in range(1, 5)
    ] + [live("test")]
    push = FakePush()
    assert process_live(repo, CONFIG, [Down()], NOW, PACKS, push=push) == 1
    req = next(r for r in repo.requests if r["id"] == "test")
    assert req["status"] == "done"
    assert [d["outcome"] for d in req["result"]["devices"]] == ["sent", "removed", "failed"]
    assert "SECRET" not in json.dumps(req["result"])
    assert {r["status"] for r in repo.requests if r["id"] != "test"} == {"pending"}
    assert len(push.sent) == 1


def test_live_request_failures_say_why() -> None:
    repo = MemoryRepo(CONFIG)
    repo.requests = [
        live("nokey"),
        live("bad", payload={"kind": "fireworks"}),
        live("old", created_at=NOW - timedelta(days=2)),
    ]
    process_live(repo, CONFIG, [], NOW, PACKS, push=None)
    by_id = {r["id"]: r for r in repo.requests}
    assert by_id["nokey"]["status"] == "failed" and "VAPID" in by_id["nokey"]["error"]
    assert (by_id["bad"]["status"], by_id["bad"]["error"]) == ("failed", "ValidationError")
    assert by_id["old"]["status"] == "cancelled"
