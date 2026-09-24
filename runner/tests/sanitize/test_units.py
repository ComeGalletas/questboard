"""Sanitizer building blocks: checksums, tokens, text preparation, no false drops."""

from __future__ import annotations

from runner.sanitize import MemoryVault, detect_lang, log_rows, sanitize
from runner.sanitize.recognizers import iban_ok, luhn_ok, nit_check_digit, nit_ok
from runner.sanitize.text import cap, html_to_text, strip_replies_and_signature
from runner.sanitize.vault import value_hash


def test_checksums() -> None:
    assert luhn_ok("4111 1111 1111 1111") and not luhn_ok("4111 1111 1111 1112")
    assert iban_ok("GB82 WEST 1234 5698 7654 32") and not iban_ok("GB82 WEST 1234 5698 7654 33")
    assert nit_check_digit("900373913") == 4
    assert nit_ok("900.373.913-4") and not nit_ok("900.373.913-5")


def test_tokens_are_stable_per_value_and_salted() -> None:
    vault = MemoryVault()
    a = sanitize("Llame al 300 123 4567 o al 3001234567.", vault)
    b = sanitize("Mi número: +57 300-123-4567", vault)
    assert a.text == "Llame al PHONE_1 o al PHONE_1."
    assert b.text.endswith("PHONE_1")
    other = MemoryVault()
    assert value_hash(vault.salt, "PHONE", "3001234567") != value_hash(
        other.salt, "PHONE", "3001234567"
    )
    assert vault.value_of("PHONE_1") == "300 123 4567"


def test_dates_times_and_short_numbers_survive() -> None:
    out = sanitize("Vence el 05/10/2026 a las 18:30, piso 4, 2 cuotas, año 2026.", MemoryVault())
    assert out.text == "Vence el 05/10/2026 a las 18:30, piso 4, 2 cuotas, año 2026."
    assert out.drop is None


def test_no_false_credential_drops() -> None:
    for text in (
        "Use el código de pago 5566778 en cualquier corresponsal.",
        "Password reset requested? Ignore this email if it wasn't you.",
        "Recuerda cambiar el PIN de tu tarjeta en la app.",
    ):
        assert sanitize(text, MemoryVault()).drop is None, text


def test_strip_and_html() -> None:
    text, fired = strip_replies_and_signature("Hecho.\n> cita previa\nSaludos,\nAna\n300 1")
    assert text == "Hecho." and fired == ["strip.quoted_lines", "strip.signature"]
    assert html_to_text("<p>Hola</p><script>x()</script><p>a&nbsp;b</p>") == "Hola\n\na\xa0b"


def test_cap_cuts_at_whitespace() -> None:
    capped, cut = cap("palabra " * 200)
    assert cut and len(capped) <= 802 and capped.endswith("palabra …")


def test_language_and_log_rows() -> None:
    assert detect_lang("Your invoice is ready for payment") == "en"
    assert detect_lang("Su factura está lista para el pago") == "es"
    out = sanitize("Hola Juan Pablo, su cédula 1.020.304.050 quedó registrada.", MemoryVault())
    rows = log_rows(out, "utilities")
    assert {r["rule"] for r in rows} >= {"idnum.context"}
    assert all(set(r) == {"profile", "rule", "hits", "messages"} for r in rows)
    assert "1.020.304.050" not in str(rows) and "Juan" not in str(rows)


def test_nothing_personal_reaches_the_logs(caplog) -> None:
    import logging

    caplog.set_level(logging.DEBUG)
    sanitize("Hola Juan Secretname, cédula 1.020.304.050, clave: Zz9!abcd", MemoryVault())
    logged = " ".join(r.getMessage() for r in caplog.records)
    for value in ("Secretname", "1.020.304.050", "Zz9!abcd"):
        assert value not in logged
