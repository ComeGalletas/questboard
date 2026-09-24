"""Token <-> value vault interface. Tokens are stable per value: the same person, amount or
account always gets the same token (PERSON_7), so quests and completion signals line up
across emails.

value_hash = HMAC-SHA256(salt, kind + canonical value). The salt never leaves this machine,
so a hash in a log or the cloud cannot be brute-forced back into a cédula or a phone number.
The persistent vault (SQLCipher, key in the OS keychain) implements the same protocol.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field
from typing import Protocol

# Kinds whose identity is the digits alone ("300 123 4567" == "3001234567").
NUMERIC_KINDS = frozenset({"PHONE", "IDNUM", "TAXID", "CARD", "ACCOUNT", "REF"})


def canonical(kind: str, value: str) -> str:
    if kind in NUMERIC_KINDS:
        digits = re.sub(r"[^0-9A-Za-z]", "", value).upper()
        if kind == "PHONE" and len(digits) == 12 and digits.startswith("57"):
            digits = digits[2:]  # +57 300… is the same line as 300…
        return digits
    if kind == "EMAIL":
        return re.sub(r"\s+", "", value).lower()
    if kind == "IBAN":
        return re.sub(r"\s+", "", value).upper()
    return re.sub(r"\s+", " ", value).strip().casefold()


def value_hash(salt: bytes, kind: str, value: str) -> str:
    msg = f"{kind}\0{canonical(kind, value)}".encode()
    return hmac.new(salt, msg, hashlib.sha256).hexdigest()


class Vault(Protocol):
    def token_for(self, kind: str, value: str) -> str:
        """The stable token for this value, minting KIND_<n> the first time it is seen."""
        ...


@dataclass
class MemoryVault:
    """In-memory vault for tests and dry runs. Same token rules as the persistent one."""

    salt: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    _tokens: dict[str, str] = field(default_factory=dict)
    _values: dict[str, str] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)

    def token_for(self, kind: str, value: str) -> str:
        key = value_hash(self.salt, kind, value)
        token = self._tokens.get(key)
        if token is None:
            n = self._counters.get(kind, 0) + 1
            self._counters[kind] = n
            token = f"{kind}_{n}"
            self._tokens[key] = token
            self._values[token] = value
        return token

    def value_of(self, token: str) -> str | None:
        """Re-hydration: PC UI only (never the phone, never a prompt)."""
        return self._values.get(token)
