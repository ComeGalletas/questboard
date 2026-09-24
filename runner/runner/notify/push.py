"""Web Push delivery (VAPID). The private key is machine-local: QUESTBOARD_VAPID_PRIVATE_KEY
(base64url, as printed by `python -m runner vapid`). Messages carry the notification's own
title/body/target only; payloads are end-to-end encrypted to the browser."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

SUBJECT = "mailto:questboard@localhost"


class Gone(Exception):
    """The push service says this subscription no longer exists (404/410)."""


Sender = Callable[[dict[str, Any], bytes], None]


def webpush_sender(private_key: str, subject: str = SUBJECT) -> Sender:
    from pywebpush import WebPushException, webpush

    def send(sub: dict[str, Any], payload: bytes) -> None:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
                ttl=6 * 3600,
                timeout=10,
            )
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                raise Gone() from None
            raise RuntimeError(f"push failed ({status})") from None

    return send


def sender_from_env() -> Sender | None:
    key = os.environ.get("QUESTBOARD_VAPID_PRIVATE_KEY")
    return webpush_sender(key) if key else None


@dataclass(frozen=True)
class PushResult:
    sent: int = 0
    removed: int = 0
    failed: int = 0


def payload(notification: dict[str, Any]) -> bytes:
    return json.dumps(
        {
            "kind": notification["kind"],
            "title": notification.get("title") or "Questboard",
            "body": notification.get("body") or "",
            "target": notification["target"],
            "persona": notification.get("persona"),
        },
        separators=(",", ":"),
    ).encode()


def generate_vapid_keys() -> tuple[str, str]:
    """(private, public) base64url keys for VAPID (public goes to the web app build)."""
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    raw_private = key.private_numbers().private_value.to_bytes(32, "big")
    raw_public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )

    def b64(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    return b64(raw_private), b64(raw_public)
