"""Custom recognizers (regex + checksums) for what spaCy NER cannot see: Colombian IDs (cédula,
NIT), CO phones, Luhn-valid cards, IBANs, amounts, addresses, account / reference numbers,
one-time codes and passwords. Each rule has a name that goes to sanitization_log (never the
value). They are Presidio recognizers so the NER and the rules run in one pass.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from presidio_analyzer import EntityRecognizer, RecognizerResult

# -- checksums ----------------------------------------------------------------------------------


def digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def luhn_ok(number: str) -> bool:
    d = digits(number)
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def iban_ok(value: str) -> bool:
    s = re.sub(r"\s+", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return False
    rearranged = s[4:] + s[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


_NIT_WEIGHTS = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def nit_check_digit(base: str) -> int:
    """DIAN check digit (dígito de verificación) for a NIT."""
    total = sum(int(d) * w for d, w in zip(reversed(digits(base)), _NIT_WEIGHTS, strict=False))
    r = total % 11
    return r if r in (0, 1) else 11 - r


def nit_ok(value: str) -> bool:
    d = digits(value)
    return len(d) == 10 and nit_check_digit(d[:9]) == int(d[9])


# -- rules --------------------------------------------------------------------------------------

_NAME = r"[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'-]+"
NAMES = rf"{_NAME}(?:[ \t]+(?:(?:de|del|de[ \t]+la)[ \t]+)?{_NAME}){{0,4}}"
_NUM_LABEL = r"(?:(?i:no|n[°º]|nro|number|num|n[úu]mero|id)\.?[ \t]*|#[ \t]*)?[:.]?[ \t]*"


@dataclass(frozen=True)
class Rule:
    name: str  # sanitization_log rule
    kind: str  # token kind (PERSON, CARD, ...) or SECRET
    pattern: re.Pattern[str]
    group: int = 0
    score: float = 0.9
    valid: Callable[[str], bool] | None = None


def _r(pattern: str, flags: int = 0) -> re.Pattern[str]:
    return re.compile(pattern, flags)


RULES: list[Rule] = [
    # Secrets: never tokenized, never stored. A hit drops the whole message (credentials).
    Rule(
        "secret.otp",
        "SECRET",
        _r(
            r"(?i:c[óo]digo[ \t]+de[ \t]+(?:verificaci[óo]n|seguridad|acceso|confirmaci[óo]n|"
            r"autenticaci[óo]n|un[ \t]+solo[ \t]+uso)|verification[ \t]+code|security[ \t]+code|"
            r"one[- ]time[ \t]+(?:code|password|passcode)|\botp\b|\bpin\b|"
            r"clave[ \t]+din[áa]mica|\btoken\b|passcode|(?:your|tu|su)[ \t]+(?:code|c[óo]digo)|"
            r"(?:code|c[óo]digo)[ \t]+(?:is|es))"
            r"[^\n\d]{0,25}?(?<![\w-])((?:[A-Z]{1,3}-)?[A-Z0-9]{4,8})(?![\w-])"
        ),
        group=1,
        valid=lambda s: any(c.isdigit() for c in s),
    ),
    Rule(
        "secret.password",
        "SECRET",
        _r(
            r"(?i:contrase[ñn]a|password|passwd|clave)(?i:[ \t]+(?:temporal|provisional|"
            r"temporary|nueva|new))?(?i:[ \t]+(?:es|is))?[ \t]*[:=][ \t]*(\S{4,64})"
        ),
        group=1,
    ),
    Rule(
        "secret.password_is",
        "SECRET",
        _r(
            r"(?i:contrase[ñn]a|password|clave)(?i:[ \t]+(?:temporal|provisional|temporary))?"
            r"[ \t]+(?i:es|is)[ \t]+(\S{4,64})"
        ),
        group=1,
    ),
    # Payment instruments and government ids.
    Rule(
        "card.luhn",
        "CARD",
        _r(r"(?<![\d])(?:\d[ \t-]?){12,18}\d(?![\d])"),
        valid=luhn_ok,
    ),
    Rule(
        "iban.mod97",
        "IBAN",
        _r(r"\b[A-Z]{2}\d{2}(?:[ \t]?[A-Z0-9]{4}){2,7}(?:[ \t]?[A-Z0-9]{1,3})?\b"),
        valid=iban_ok,
    ),
    Rule(
        "taxid.nit_dv",
        "TAXID",
        _r(r"(?<![\d.])\d{3}\.?\d{3}\.?\d{3}[ \t]?-[ \t]?\d(?![\d])"),
        valid=nit_ok,
    ),
    Rule(
        "taxid.nit_context",
        "TAXID",
        _r(rf"(?i:\bnit\b)\.?[ \t]*{_NUM_LABEL}(\d{{3}}\.?\d{{3}}\.?\d{{3}}(?:[ \t]?-[ \t]?\d)?)"),
        group=1,
    ),
    Rule(
        "idnum.context",
        "IDNUM",
        _r(
            r"(?i:c[ée]dula(?:[ \t]+de[ \t]+(?:ciudadan[ií]a|extranjer[ií]a))?|\bc\.[ \t]?c\b\.?|"
            r"\bcc\b|\bc\.?e\b\.?|documento(?:[ \t]+de[ \t]+identidad)?|identificaci[óo]n|"
            r"\bdoc\b\.?|pasaporte|passport|licencia|driver'?s[ \t]+license|\bssn\b|"
            r"tarjeta[ \t]+de[ \t]+identidad)"
            rf"[ \t]*{_NUM_LABEL}([A-Z]{{0,2}}\d(?:[\d. -]{{3,14}}\d))"
        ),
        group=1,
        valid=lambda s: len(digits(s)) >= 5,
    ),
    Rule("idnum.ssn", "IDNUM", _r(r"(?<![\d-])\d{3}-\d{2}-\d{4}(?![\d-])")),
    # Contact details.
    Rule("email.address", "EMAIL", _r(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    Rule(
        "email.obfuscated",
        "EMAIL",
        _r(
            r"[\w.+-]+[ \t]*(?:\[at\]|\(at\)|\{at\}|[ \t]arroba[ \t])[ \t]*[\w-]+"
            r"(?:[ \t]*(?:\.|\[dot\]|\(dot\)|[ \t]punto[ \t])[ \t]*[\w-]+)+",
            re.IGNORECASE,
        ),
    ),
    Rule("url", "URL", _r(r"\b(?:https?://|www\.)[^\s<>\"')\]]+", re.IGNORECASE)),
    Rule(
        "phone.co_mobile",
        "PHONE",
        _r(
            r"(?<![\w+])(?:\+?57[ \t.-]?)?\(?3\d{2}\)?"
            r"[ \t.-]?\d{3}[ \t.-]?\d{2}[ \t.-]?\d{2}(?![\w])"
        ),
    ),
    Rule(
        "phone.co_landline",
        "PHONE",
        _r(r"(?<![\w+])(?:\+?57[ \t.-]?)?\(?60[1-8]\)?[ \t.-]?\d{3}[ \t.-]?\d{4}(?![\w])"),
    ),
    Rule(
        "phone.international",
        "PHONE",
        _r(r"(?<![\w])\+\d{1,3}(?:[ \t.-]?\(?\d{1,4}\)?){2,5}(?![\w])"),
        valid=lambda s: 8 <= len(digits(s)) <= 15,
    ),
    Rule("phone.us", "PHONE", _r(r"(?<![\w])\(?\d{3}\)?[ \t.-]\d{3}[ \t.-]\d{4}(?![\w])")),
    # Money: tokenized (the extractor turns AMOUNT_n into a bill; the value stays in the vault).
    Rule(
        "amount.currency",
        "AMOUNT",
        _r(
            r"(?:\b(?:COP|USD|EUR|MXN)|US\$|COL\$|\$|€|£)[ \t]?(?:\d[\d.,]*\d|\d)"
            r"|\b\d[\d.,]*\d[ \t]?(?:COP|USD|EUR|MXN|pesos|d[óo]lares|dollars|euros)\b"
        ),
    ),
    Rule(
        "amount.context",
        "AMOUNT",
        _r(
            r"(?i:total(?:[ \t]+a[ \t]+pagar)?|valor(?:[ \t]+a[ \t]+pagar)?|saldo|monto|"
            r"importe|amount(?:[ \t]+due)?|balance(?:[ \t]+due)?)[ \t]*:?[ \t]*"
            r"(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+[.,]\d{2})(?![\d])"
        ),
        group=1,
    ),
    # Places.
    Rule(
        "address.co",
        "ADDRESS",
        _r(
            r"(?i:\b(?:calle|cll|cl|carrera|cra|kra|kr|cr|avenida(?:[ \t]+(?:calle|carrera))?|"
            r"av|ak|ac|diagonal|dg|transversal|tv|tr|circular|circunvalar)\b\.?)"
            r"[ \t]*\d{1,3}[ \t]*[A-Za-z]?(?:[ \t]*(?i:bis|sur|este|norte|oeste)\b)*[ \t]*"
            r"(?:#|(?i:no\.?|n[°º]|n[úu]mero))[ \t]*\d{1,3}[ \t]*[A-Za-z]?"
            r"(?:[ \t]*(?i:bis|sur|este|norte|oeste)\b)?[ \t]*-[ \t]*\d{1,3}"
            r"(?:[ \t]*(?i:sur|este|norte|oeste)\b)?"
            r"(?:[ \t]*,?[ \t]*(?i:apto|apartamento|apt|int|interior|casa|torre|piso|oficina|of|"
            r"local)\.?[ \t]*\w{1,6})*"
        ),
    ),
    Rule(
        "address.en",
        "ADDRESS",
        _r(
            r"\b\d{1,6}[ \t]+(?:[A-Z][a-z]+[ \t]+){1,3}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|"
            r"Boulevard|Ln|Lane|Dr|Drive|Way|Ct|Court|Pl|Place)\b\.?"
            r"(?:,?[ \t]*(?:Apt|Suite|Unit|#)\.?[ \t]*\w{1,6})?"
        ),
    ),
    # Account and reference numbers (references let extractors match completion signals).
    Rule(
        "account.bank",
        "ACCOUNT",
        _r(
            r"(?i:cuenta(?:[ \t]+(?:de[ \t]+)?(?:ahorros|corriente))?|account|acct|a/c)"
            rf"[ \t]*{_NUM_LABEL}(\d[\d -]{{4,22}}\d)"
        ),
        group=1,
        valid=lambda s: len(digits(s)) >= 6,
    ),
    Rule(
        "ref.context",
        "REF",
        _r(
            r"(?i:contrato|contract|p[óo]liza|policy|cliente|customer|suscriptor|subscriber|"
            r"referencia|reference|\bref\b|factura|invoice|pedido|order|gu[ií]a|tracking|"
            r"seguimiento|radicado|expediente|caso|case|ticket|matr[ií]cula|convenio|"
            r"c[óo]digo[ \t]+de[ \t]+pago)"
            rf"[ \t]*{_NUM_LABEL}([A-Z0-9](?:[A-Z0-9-]{{2,24}})[A-Z0-9])(?![\w-])"
        ),
        group=1,
        valid=lambda s: len(digits(s)) >= 4,
    ),
    # Names the NER tends to miss: after a greeting or a label ("Paciente: …").
    Rule(
        "person.salutation",
        "PERSON",
        _r(
            r"(?i:\b(?:hola|buen[oa]s?[ \t]+(?:d[ií]as|tardes|noches)|estimad[oa]s?|"
            r"apreciad[oa]s?|querid[oa]s?|señor(?:a|ita)?|sr|sra|srta|dr|dra|doctor(?:a)?|"
            r"dear|hi|hello|hey|mr|mrs|ms|miss))\.?[ \t]*[,:]?[ \t]*(?:\([ao]\)[ \t]*[:,]?[ \t]*)?"
            rf"({NAMES})"
        ),
        group=1,
        score=0.8,
    ),
    Rule(
        "person.label",
        "PERSON",
        _r(
            r"(?i:paciente|nombre(?:[ \t]+completo)?|full[ \t]+name|\bname|titular|"
            r"destinatario|recipient|attn|atenci[óo]n|a[ \t]+nombre[ \t]+de|beneficiario|"
            r"estudiante|student|alumno|cliente|customer|usuario)[ \t]*[:.-]?[ \t]*"
            rf"({NAMES})"
        ),
        group=1,
        score=0.8,
    ),
]


class RegexRecognizer(EntityRecognizer):
    """One Rule as a Presidio recognizer; the rule name travels in recognition_metadata."""

    def __init__(self, rule: Rule, language: str):
        self.rule = rule
        super().__init__(
            supported_entities=[rule.kind],
            name=f"questboard:{rule.name}",
            supported_language=language,
        )

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
        if self.rule.kind not in entities:
            return []
        out = []
        for m in self.rule.pattern.finditer(text):
            start, end = m.span(self.rule.group)
            value = text[start:end]
            if start == end or (self.rule.valid and not self.rule.valid(value)):
                continue
            out.append(
                RecognizerResult(
                    self.rule.kind,
                    start,
                    end,
                    self.rule.score,
                    recognition_metadata={
                        RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                        "rule": self.rule.name,
                    },
                )
            )
        return out
