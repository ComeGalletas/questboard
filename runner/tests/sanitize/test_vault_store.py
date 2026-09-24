"""vault.db: SQLCipher file + AES-GCM values, stable tokens across restarts."""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest

from runner.sanitize import SqlCipherVault, VaultError, sanitize
from runner.sanitize.vault_store import StaticMasterKey

KEY = StaticMasterKey(secrets.token_bytes(32))


def test_tokens_are_stable_across_restarts(tmp_path: Path) -> None:
    path = tmp_path / "vault.db"
    with SqlCipherVault(path, KEY) as v:
        a = v.token_for("PHONE", "300 123 4567")
        b = v.token_for("PERSON", "Ana María Restrepo")
        assert (a, b) == ("PHONE_1", "PERSON_1")
        assert v.token_for("PHONE", "+57 300-123-4567") == "PHONE_1"
        assert v.token_for("PHONE", "310 555 7890") == "PHONE_2"
    with SqlCipherVault(path, KEY) as v:
        assert v.token_for("PERSON", "ana maría  restrepo") == "PERSON_1"
        assert v.token_for("PERSON", "Pedro Salazar") == "PERSON_2"
        assert v.value_of("PHONE_1") == "300 123 4567"
        assert v.count() == 4


def test_file_is_encrypted_and_needs_the_key(tmp_path: Path) -> None:
    path = tmp_path / "vault.db"
    with SqlCipherVault(path, KEY) as v:
        v.token_for("IDNUM", "1.020.304.050")
        v.token_for("PERSON", "Juan Pablo Pérez")
    raw = path.read_bytes()
    assert not raw.startswith(b"SQLite format 3")
    for plain in (b"1.020.304.050", "Pérez".encode(), b"PERSON_1", b"pseudonyms"):
        assert plain not in raw
    with pytest.raises(VaultError):
        SqlCipherVault(path, StaticMasterKey(secrets.token_bytes(32)))
    assert oct(path.stat().st_mode)[-3:] == "600"


def test_values_are_sealed_even_inside_the_database(tmp_path: Path) -> None:
    with SqlCipherVault(tmp_path / "vault.db", KEY) as v:
        v.token_for("CARD", "4111 1111 1111 1111")
        [(blob,)] = v._db.execute("select value_encrypted from pseudonyms").fetchall()
        assert b"4111" not in blob
        # A sealed value moved to another token does not open.
        v._db.execute("update pseudonyms set token = 'CARD_9'")
        with pytest.raises(Exception):  # noqa: B017 - cryptography's InvalidTag
            v.value_of("CARD_9")


def test_sanitize_with_the_real_vault_and_rehydrate(tmp_path: Path) -> None:
    with SqlCipherVault(tmp_path / "vault.db", KEY) as v:
        out = sanitize("Hola Laura Martínez, su cédula 52.418.993 quedó registrada.", v)
        assert "Laura" not in out.text and "52.418.993" not in out.text
        back = v.rehydrate(out.text + " ORG_99")
        assert "Laura Martínez" in back and "52.418.993" in back and back.endswith("ORG_99")


def test_bad_kind_and_key_rejected(tmp_path: Path) -> None:
    with SqlCipherVault(tmp_path / "vault.db", KEY) as v, pytest.raises(ValueError):
        v.token_for("person", "x")
    with pytest.raises(VaultError):
        SqlCipherVault(tmp_path / "other.db", StaticMasterKey(b"short"))


def test_no_keychain_is_a_clear_error(monkeypatch, tmp_path: Path) -> None:
    import keyring
    from keyring.errors import NoKeyringError

    def fail(*_a, **_k):
        raise NoKeyringError("none")

    monkeypatch.setattr(keyring, "get_password", fail)
    with pytest.raises(VaultError, match="no OS keychain"):
        SqlCipherVault(tmp_path / "vault.db")
    assert not (tmp_path / "vault.db").exists()
