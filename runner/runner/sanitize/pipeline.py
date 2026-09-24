"""The sanitizer: raw email text in, pseudonymized text out. Runs only in the runner, before
anything is stored or sent to a model (invariant 5).

  fold -> (html -> text) -> strip quoted replies / signature -> window (1200 chars)
  -> Presidio: spaCy NER (es/en) + custom recognizers -> resolve overlaps by priority
  -> replace with vault tokens (PERSON_7, AMOUNT_2 ...), secrets with [SECRET]
  -> residual pass: any leftover long number or code becomes a REF token
  -> cap at 800 chars

Only rule names and counts leave this module (sanitization_log); never values.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from runner.sanitize.recognizers import RULES, RegexRecognizer, digits
from runner.sanitize.text import (
    WINDOW,
    cap,
    fold,
    html_to_text,
    strip_replies_and_signature,
)
from runner.sanitize.vault import Vault

Lang = Literal["es", "en"]
SECRET = "[SECRET]"
MODELS = {"es": "es_core_news_md", "en": "en_core_web_md"}
NER_KINDS = {"PERSON": "PERSON", "ORGANIZATION": "ORG", "LOCATION": "LOC"}
NER_MIN_SCORE = 0.5

# Overlaps: the higher kind wins (then the longer span). Secrets and payment data first.
PRIORITY = [
    "SECRET",
    "CARD",
    "IBAN",
    "TAXID",
    "IDNUM",
    "ACCOUNT",
    "EMAIL",
    "URL",
    "PHONE",
    "AMOUNT",
    "ADDRESS",
    "REF",
    "PERSON",
    "ORG",
    "LOC",
]
_RANK = {k: i for i, k in enumerate(PRIORITY)}


def _words(s: str) -> frozenset[str]:
    return frozenset(s.split())


# Words spaCy tags as names/places in bills and letters. A span starting with one is dropped.
NOT_ENTITIES = _words(
    """
    hola estimado estimada estimados apreciado querido señor señora sr sra dr dra atentamente
    cordialmente saludos gracias dirección direccion cédula cedula factura fecha valor total
    cliente clientes usuario referencia pago pagos cuenta nit asunto vence vencimiento cita
    paciente pedido guía guia envío envio tarjeta banco dear hi hello regards thanks thank
    invoice due amount date order customer user card iban account payment subject team equipo
    amigo friend member miembro suscriptor subscriber patient total contrato plan servicio
    service recordatorio reminder aviso notice importante important
    """
)

_ES_HINTS = _words(
    "el la los las de del que en por para con su sus es una un factura pago hola gracias"
)
_EN_HINTS = _words("the and of to for your you is are with on at this invoice payment hi thanks")


def detect_lang(text: str) -> Lang:
    words = re.findall(r"[a-záéíóúñ]+", text.lower())
    es = sum(w in _ES_HINTS for w in words)
    en = sum(w in _EN_HINTS for w in words)
    return "en" if en > es else "es"


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    kind: str
    rule: str


@dataclass
class Sanitized:
    text: str
    lang: Lang
    hits: Counter[str] = field(default_factory=Counter)  # rule -> count
    drop: str | None = None  # "credentials" when a code or password was found
    truncated: bool = False


@lru_cache(maxsize=1)
def _engine():
    """Presidio with the spaCy models and our rules. Loaded once (a few seconds)."""
    logging.getLogger("presidio-analyzer").setLevel(logging.WARNING)  # recognizer lists only
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_analyzer.predefined_recognizers import SpacyRecognizer

    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": lang, "model_name": m} for lang, m in MODELS.items()],
        }
    )
    registry = RecognizerRegistry(supported_languages=list(MODELS))
    for lang in MODELS:
        registry.add_recognizer(
            SpacyRecognizer(supported_language=lang, supported_entities=list(NER_KINDS))
        )
        for rule in RULES:
            registry.add_recognizer(RegexRecognizer(rule, lang))
    return AnalyzerEngine(
        nlp_engine=provider.create_engine(),
        registry=registry,
        supported_languages=list(MODELS),
    )


def _spans(text: str, lang: Lang) -> list[Span]:
    entities = sorted({r.kind for r in RULES} | set(NER_KINDS))
    spans = []
    for r in _engine().analyze(text, language=lang, entities=entities):
        meta = r.recognition_metadata or {}
        rule = meta.get("rule")
        if rule is None:  # spaCy NER
            if r.score < NER_MIN_SCORE:
                continue
            span = _clean_ner(text, r.start, r.end)
            if span is None:
                continue
            spans.append(Span(*span, NER_KINDS[r.entity_type], f"ner.{r.entity_type.lower()}"))
        else:
            spans.append(Span(r.start, r.end, r.entity_type, rule))
    return spans


def _clean_ner(text: str, start: int, end: int) -> tuple[int, int] | None:
    value = text[start:end]
    stripped = value.strip(" \t\n.,:;!?¡¿()\"'")
    if len(stripped) < 2 or "@" in stripped or any(c.isdigit() for c in stripped):
        return None
    first = re.split(r"[^\wáéíóúñü]+", stripped.lower(), maxsplit=1)[0]
    if first in NOT_ENTITIES:
        return None
    offset = value.find(stripped)
    return start + offset, start + offset + len(stripped)


def _resolve(spans: list[Span]) -> list[Span]:
    """Non-overlapping spans: by kind priority, then longer first."""
    chosen: list[Span] = []
    for s in sorted(spans, key=lambda s: (_RANK[s.kind], -(s.end - s.start), s.start)):
        if not any(c.start < s.end and s.start < c.end for c in chosen):
            chosen.append(s)
    return sorted(chosen, key=lambda s: s.start)


_TOKEN = re.compile(r"\[SECRET\]|\b[A-Z]+_\d+\b")
_DATE = re.compile(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}[/.-]\d{1,2}[/.-]\d{1,2}")
# Space-grouped runs first ("01 8000 912 345"), then runs joined by . / -.
_RESIDUAL_NUM = re.compile(
    r"(?<![\w])\d{1,4}(?:[ \t]\d{2,4}){2,}(?![\w])|(?<![\w])\d[\d./-]*\d(?![\w])"
)
_RESIDUAL_CODE = re.compile(
    r"(?<![\w])(?=[A-Z0-9-]*\d{4})(?=[A-Z0-9-]*[A-Z])[A-Z0-9][A-Z0-9-]{6,}[A-Z0-9](?![\w])"
)
RESIDUAL_MIN_DIGITS = 7


def _residual(text: str, vault: Vault, hits: Counter[str]) -> str:
    """Anything number-like the rules did not claim: 7+ digits, or long letter+digit codes."""

    def number(m: re.Match[str]) -> str:
        value = m.group(0)
        if len(digits(value)) < RESIDUAL_MIN_DIGITS or _DATE.fullmatch(value):
            return value
        hits["residual.number"] += 1
        return vault.token_for("REF", value)

    def code(m: re.Match[str]) -> str:
        hits["residual.code"] += 1
        return vault.token_for("REF", m.group(0))

    out = []
    last = 0
    for t in _TOKEN.finditer(text):  # never touch tokens already issued
        out.append(_RESIDUAL_CODE.sub(code, _RESIDUAL_NUM.sub(number, text[last : t.start()])))
        out.append(t.group(0))
        last = t.end()
    out.append(_RESIDUAL_CODE.sub(code, _RESIDUAL_NUM.sub(number, text[last:])))
    return "".join(out)


def sanitize(
    body: str,
    vault: Vault,
    *,
    html: bool = False,
    lang: Lang | None = None,
    strip: bool = True,
) -> Sanitized:
    """Pseudonymize one text (an email body or subject). Nothing here logs or stores `body`."""
    hits: Counter[str] = Counter()
    text = fold(body)
    if html:
        text = fold(html_to_text(text))
    if strip:
        text, fired = strip_replies_and_signature(text)
        hits.update(fired)
    text = text[:WINDOW]
    language: Lang = lang or detect_lang(text)

    out, last, drop = [], 0, None
    for s in _resolve(_spans(text, language)):
        out.append(text[last : s.start])
        hits[s.rule] += 1
        if s.kind == "SECRET":
            out.append(SECRET)
            drop = "credentials"
        else:
            out.append(vault.token_for(s.kind, text[s.start : s.end]))
        last = s.end
    out.append(text[last:])
    result = _residual("".join(out), vault, hits)
    capped, truncated = cap(result)
    return Sanitized(capped, language, hits, drop, truncated)


def log_rows(result: Sanitized, profile: str) -> list[dict[str, object]]:
    """sanitization_log rows for one message: rule names and counts only."""
    return [
        {"profile": profile, "rule": rule, "hits": n, "messages": 1}
        for rule, n in sorted(result.hits.items())
    ]
