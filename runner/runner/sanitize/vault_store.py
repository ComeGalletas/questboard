"""The persistent vault: vault.db on this PC, never synced (invariant 5).

  pseudonyms(token, kind, value_hash, value_encrypted, first_seen)

Two layers of encryption, both keyed from one 32-byte master key kept in the OS keychain
(Windows Credential Manager / macOS Keychain / Secret Service):
- SQLCipher encrypts the whole file (pages, indexes, the token counters);
- each value is also sealed with AES-256-GCM (the token as associated data), so even an opened
  database or a copied row does not show a value on its own.
The hash salt is derived from the same master key, so tokens stay stable for as long as the
key does. Losing the key loses the mapping (tokens in the cloud DB then cannot be re-hydrated);
the encrypted backup/export is a Phase 7 task.

Values are only ever returned to the PC UI (re-hydration); never logged, never in a prompt.
"""

from __future__ import annotations

import base64
import os
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from runner.paths import data_dir
from runner.sanitize.vault import value_hash

KEYRING_SERVICE = "questboard-runner"
KEYRING_USER = "vault-master-key"
_KIND = re.compile(r"^[A-Z]+$")
_TOKEN = re.compile(r"\b([A-Z]+)_(\d+)\b")
_NONCE = 12

SCHEMA = """
create table if not exists pseudonyms (
  token           text primary key,
  kind            text not null,
  value_hash      text not null unique,
  value_encrypted blob not null,
  first_seen      text not null
);
create table if not exists counters (
  kind text primary key,
  n    integer not null
);
"""


class VaultError(Exception):
    """The vault cannot be opened (wrong or missing key, corrupt file). Messages carry no data."""


class MasterKey(Protocol):
    def get(self) -> bytes: ...


class KeyringMasterKey:
    """The master key in the OS keychain; created on first use. Tauri reads the same entry."""

    def get(self) -> bytes:
        import keyring
        from keyring.errors import KeyringError

        try:
            stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
            if stored:
                return base64.b64decode(stored)
            key = secrets.token_bytes(32)
            keyring.set_password(KEYRING_SERVICE, KEYRING_USER, base64.b64encode(key).decode())
        except KeyringError:
            # Never fall back to a key file next to the vault: that would defeat the encryption.
            raise VaultError("no OS keychain available for the vault key") from None
        return key


@dataclass(frozen=True)
class StaticMasterKey:
    """Tests and tools only."""

    key: bytes

    def get(self) -> bytes:
        return self.key


def _derive(master: bytes, purpose: str) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=f"questboard/{purpose}".encode()
    )
    return hkdf.derive(master)


def default_path() -> Path:
    return data_dir() / "vault.db"


class SqlCipherVault:
    """`Vault` backed by vault.db. One runner instance holds it (the runner lock file)."""

    def __init__(self, path: Path | None = None, master: MasterKey | None = None):
        import sqlcipher3

        key = (master or KeyringMasterKey()).get()
        if len(key) != 32:
            raise VaultError("vault master key must be 32 bytes")
        self.salt = _derive(key, "hash-salt")
        self._aead = AESGCM(_derive(key, "values"))
        self.path = path or default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlcipher3.connect(str(self.path), isolation_level=None)
        self._db.execute(f"pragma key = \"x'{_derive(key, 'sqlcipher').hex()}'\"")
        try:
            self._db.execute("select count(*) from sqlite_master").fetchone()
        except sqlcipher3.DatabaseError:
            self._db.close()
            raise VaultError("vault.db does not open with this key") from None
        self._db.executescript(SCHEMA)
        if os.name == "posix":
            os.chmod(self.path, 0o600)

    # -- Vault ---------------------------------------------------------------------------------

    def token_for(self, kind: str, value: str) -> str:
        if not _KIND.match(kind):
            raise ValueError("token kind must be upper-case letters")
        h = value_hash(self.salt, kind, value)
        row = self._db.execute("select token from pseudonyms where value_hash = ?", (h,)).fetchone()
        if row:
            return row[0]
        self._db.execute("begin immediate")
        try:
            row = self._db.execute(
                "select token from pseudonyms where value_hash = ?", (h,)
            ).fetchone()
            if row:
                self._db.execute("commit")
                return row[0]
            current = self._db.execute("select n from counters where kind = ?", (kind,)).fetchone()
            n = (current[0] if current else 0) + 1
            token = f"{kind}_{n}"
            self._db.execute(
                "insert into counters (kind, n) values (?, ?) "
                "on conflict (kind) do update set n = excluded.n",
                (kind, n),
            )
            self._db.execute(
                "insert into pseudonyms (token, kind, value_hash, value_encrypted, first_seen) "
                "values (?, ?, ?, ?, ?)",
                (token, kind, h, self._seal(token, value), datetime.now(UTC).isoformat()),
            )
            self._db.execute("commit")
        except BaseException:
            self._db.execute("rollback")
            raise
        return token

    # -- re-hydration (PC UI only) ---------------------------------------------------------------

    def value_of(self, token: str) -> str | None:
        row = self._db.execute(
            "select value_encrypted from pseudonyms where token = ?", (token,)
        ).fetchone()
        return self._open(token, row[0]) if row else None

    def rehydrate(self, text: str) -> str:
        """Tokens back to values, for display on this PC. Unknown tokens stay as they are."""

        def swap(m: re.Match[str]) -> str:
            value = self.value_of(m.group(0))
            return value if value is not None else m.group(0)

        return _TOKEN.sub(swap, text)

    def count(self) -> int:
        return self._db.execute("select count(*) from pseudonyms").fetchone()[0]

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> SqlCipherVault:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- sealing ---------------------------------------------------------------------------------

    def _seal(self, token: str, value: str) -> bytes:
        nonce = secrets.token_bytes(_NONCE)
        return nonce + self._aead.encrypt(nonce, value.encode(), token.encode())

    def _open(self, token: str, blob: bytes) -> str:
        return self._aead.decrypt(blob[:_NONCE], blob[_NONCE:], token.encode()).decode()
