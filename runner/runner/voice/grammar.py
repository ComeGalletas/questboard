"""Deterministic voice grammar (P2, es/en) for the runner's transcripts.

Mirrors apps/web/src/voice/grammar.ts; both are locked to packages/schema/fixtures/voice.json.
The output is only ever shown on a confirmation card: voice never writes by itself (invariant 8).
Dates are parsed here rather than with dateparser so both sides agree exactly on the same words.
Transcripts are never logged or stored.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from questboard_schema.voice_command_schema import VoiceCommand

Lang = Literal["en", "es"]
Phrase = tuple[str, ...]


@dataclass(frozen=True)
class Tok:
    raw: str
    norm: str


@dataclass
class When:
    date: str | None = None
    time: str | None = None


# -- lexicon ------------------------------------------------------------------------------------

WEEKDAYS = {
    "en": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
    "es": ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"],
}
MONTHS = {
    "en": [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ],
    "es": [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ],
}
_EN_WORDS = [
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
]
_ES_WORDS = [
    "uno",
    "dos",
    "tres",
    "cuatro",
    "cinco",
    "seis",
    "siete",
    "ocho",
    "nueve",
    "diez",
    "once",
    "doce",
    "trece",
    "catorce",
    "quince",
    "dieciseis",
    "diecisiete",
    "dieciocho",
    "diecinueve",
    "veinte",
    "veintiuno",
    "veintidos",
    "veintitres",
    "veinticuatro",
    "veinticinco",
    "veintiseis",
    "veintisiete",
    "veintiocho",
    "veintinueve",
]
UNITS: dict[str, dict[str, int]] = {
    "en": {
        "a": 1,
        "an": 1,
        **{w: i + 1 for i, w in enumerate(_EN_WORDS)},
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "ninety": 90,
    },
    "es": {
        "un": 1,
        "una": 1,
        **{w: i + 1 for i, w in enumerate(_ES_WORDS)},
        "treinta": 30,
        "cuarenta": 40,
        "cincuenta": 50,
        "sesenta": 60,
        "noventa": 90,
    },
}


def _p(*alts: str) -> list[Phrase]:
    return [tuple(a.split(" ")) for a in alts]


@dataclass(frozen=True)
class Grammar:
    create: list[Phrase]
    create_filler: list[list[Phrase]]
    complete: list[Phrase]
    complete_tail: list[Phrase]
    snooze_only: list[Phrase]
    defer_only: list[Phrase]
    either: list[Phrase]
    whats_next: list[Phrase]
    confirm: list[Phrase]
    cancel: list[Phrase]
    date_prefix: list[Phrase]
    duration_prefix: list[Phrase]
    connectors: tuple[str, ...]
    articles: tuple[str, ...]
    polite: list[Phrase]


GRAMMAR: dict[str, Grammar] = {
    "en": Grammar(
        create=_p("create", "add", "new", "make"),
        create_filler=[_p("a", "an", "new"), _p("task", "quest", "todo", "to do"), _p("to")],
        complete=_p(
            "complete",
            "completed",
            "finish",
            "finished",
            "done with",
            "done",
            "mark",
            "check off",
            "i finished",
            "i completed",
            "i did",
            "im done with",
            "i am done with",
        ),
        complete_tail=_p("as done", "as complete", "as completed", "as finished", "done"),
        snooze_only=_p("snooze", "remind me about"),
        defer_only=_p("defer", "move", "push", "reschedule"),
        either=_p("postpone"),
        whats_next=_p(
            "whats next",
            "what is next",
            "what now",
            "what should i do",
            "what should i do next",
            "what should i do now",
            "next quest",
            "next task",
            "whats my next quest",
            "whats my next task",
        ),
        confirm=_p(
            "confirm", "confirmed", "yes", "yeah", "yep", "do it", "ok", "okay", "sure", "go ahead"
        ),
        cancel=_p("cancel", "no", "stop", "never mind", "nevermind", "forget it"),
        date_prefix=_p("on", "for", "by"),
        duration_prefix=_p("for", "in"),
        connectors=("on", "for", "by", "at", "to", "until", "till"),
        articles=("the", "my"),
        polite=_p("please"),
    ),
    "es": Grammar(
        create=_p(
            "crear",
            "crea",
            "agregar",
            "agrega",
            "anadir",
            "anade",
            "nueva",
            "nuevo",
            "anota",
            "anotar",
        ),
        create_filler=[
            _p("una", "un", "la", "el", "nueva"),
            _p("tarea", "mision", "quest", "pendiente"),
            _p("de", "para"),
        ],
        complete=_p(
            "completar",
            "completa",
            "complete",
            "terminar",
            "termina",
            "termine",
            "ya termine",
            "ya hice",
            "hice",
            "marcar",
            "marca",
        ),
        complete_tail=_p(
            "como hecha",
            "como hecho",
            "como completada",
            "como completado",
            "como terminada",
            "como terminado",
        ),
        snooze_only=_p("recuerdame"),
        defer_only=_p(
            "aplazar", "aplaza", "pasar", "pasa", "mover", "mueve", "reprogramar", "reprograma"
        ),
        either=_p("posponer", "pospon"),
        whats_next=_p(
            "que sigue",
            "que hago",
            "que hago ahora",
            "que debo hacer",
            "que debo hacer ahora",
            "siguiente",
            "siguiente tarea",
            "siguiente mision",
            "que es lo siguiente",
            "lo siguiente",
            "cual es la siguiente tarea",
        ),
        confirm=_p(
            "confirmar",
            "confirmo",
            "confirma",
            "si",
            "dale",
            "hazlo",
            "vale",
            "ok",
            "de acuerdo",
            "listo",
        ),
        cancel=_p("cancelar", "cancela", "no", "olvidalo", "detente"),
        date_prefix=_p("para el", "hasta el", "el", "al", "para", "hasta"),
        duration_prefix=_p("por", "durante", "en"),
        connectors=("el", "para", "a", "al", "hasta", "de", "por", "en"),
        articles=("el", "la", "los", "las", "mi", "mis"),
        polite=_p("por favor"),
    ),
}

# -- tokens -------------------------------------------------------------------------------------


def normalize(s: str) -> str:
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def tokenize(text: str) -> list[Tok]:
    spaced = re.sub(r"\b([ap])\.m\.", r"\1m", text, flags=re.IGNORECASE)
    spaced = re.sub(r"(\d)(am|pm)\b", r"\1 \2", spaced, flags=re.IGNORECASE)
    spaced = re.sub(r'[¿¡?!.,;"()]+', " ", spaced)
    spaced = re.sub(r":(?!\d)", " ", spaced)
    out: list[Tok] = []
    for raw in spaced.split():
        norm = normalize(raw).replace("'", "").replace("’", "").replace("-", " ")
        if " " in norm:
            out += [Tok(n, n) for n in norm.split(" ") if n]
        elif norm:
            out.append(Tok(raw, norm))
    return out


def _at(toks: list[Tok], i: int) -> str | None:
    return toks[i].norm if 0 <= i < len(toks) else None


def lead(toks: list[Tok], i: int, phrases: list[Phrase]) -> int:
    best = 0
    for ph in phrases:
        if len(ph) > best and all(_at(toks, i + k) == w for k, w in enumerate(ph)):
            best = len(ph)
    return best


def whole(toks: list[Tok], phrases: list[Phrase]) -> bool:
    return len(toks) > 0 and lead(toks, 0, phrases) == len(toks)


def tail(toks: list[Tok], phrases: list[Phrase]) -> int:
    best = 0
    for ph in phrases:
        start = len(toks) - len(ph)
        if (
            len(ph) > best
            and start >= 0
            and all(toks[start + k].norm == w for k, w in enumerate(ph))
        ):
            best = len(ph)
    return best


# -- numbers, dates, times ----------------------------------------------------------------------


def number(toks: list[Tok], i: int, lang: Lang) -> tuple[int, int] | None:
    t = _at(toks, i)
    if t is None:
        return None
    if re.fullmatch(r"\d{1,4}", t):
        return int(t), 1
    units = UNITS[lang]
    v = units.get(t)
    if v is None:
        return None
    if v >= 20 and v % 10 == 0 and v < 100:
        joiner = 1 if lang == "es" and _at(toks, i + 1) == "y" else 0
        nxt_word = _at(toks, i + 1 + joiner) or ""
        nxt = units.get(nxt_word)
        if nxt is not None and 1 <= nxt <= 9 and len(nxt_word) > 1:
            return v + nxt, 2 + joiner
    return v, 1


def _iso(d: date) -> str:
    return d.isoformat()


def _add_days(today: str, n: int) -> str:
    return _iso(date.fromisoformat(today) + timedelta(days=n))


def _next_weekday(today: str, wd: int) -> str:
    """The next `wd` (Monday = 0) strictly after today."""
    t = date.fromisoformat(today)
    diff = (wd - t.weekday()) % 7 or 7
    return _iso(t + timedelta(days=diff))


def _day_of_month(today: str, month: int, day: int) -> str | None:
    t = date.fromisoformat(today)
    for year in (t.year, t.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d >= t:
            return _iso(d)
    return None


def _day_of_any_month(today: str, day: int) -> str | None:
    t = date.fromisoformat(today)
    for k in range(3):
        month = (t.month - 1 + k) % 12 + 1
        year = t.year + (t.month - 1 + k) // 12
        try:
            d = date(year, month, day)
        except ValueError:
            continue
        if d >= t:
            return _iso(d)
    return None


def _day_number(toks: list[Tok], i: int, lang: Lang) -> tuple[int, int] | None:
    ordinal = re.fullmatch(r"(\d{1,2})(st|nd|rd|th)", _at(toks, i) or "")
    if ordinal and lang == "en":
        return int(ordinal.group(1)), 1
    n = number(toks, i, lang)
    return n if n and 1 <= n[0] <= 31 else None


def _index(words: list[str], w: str | None) -> int:
    return words.index(w) if w in words else -1


def date_piece(toks: list[Tok], i: int, today: str, lang: Lang) -> tuple[str, int] | None:
    pre = lead(toks, i, GRAMMAR[lang].date_prefix)
    for skip in (pre, 0) if pre > 0 else (0,):
        r = _date_piece_bare(toks, i + skip, today, lang)
        if r:
            return r[0], r[1] + skip
    return None


def _date_piece_bare(toks: list[Tok], i: int, today: str, lang: Lang) -> tuple[str, int] | None:
    def at(k: int) -> str | None:
        return _at(toks, i + k)

    weekdays, months = WEEKDAYS[lang], MONTHS[lang]

    if lang == "en":
        if at(0) in ("today", "tonight"):
            return today, 1
        if at(0) == "tomorrow":
            return _add_days(today, 1), 1
        if (at(0), at(1), at(2), at(3)) == ("the", "day", "after", "tomorrow"):
            return _add_days(today, 2), 4
        if (at(0), at(1), at(2)) == ("day", "after", "tomorrow"):
            return _add_days(today, 2), 3
        if (at(0), at(1)) == ("next", "week"):
            return _next_weekday(today, 0), 2
        mod = 1 if at(0) in ("this", "next", "coming") else 0
        wd = _index(weekdays, at(mod))
        if wd >= 0:
            return _next_weekday(today, wd), mod + 1
        if at(0) == "in":
            n = number(toks, i + 1, lang)
            if n:
                unit = at(1 + n[1])
                if unit in ("day", "days"):
                    return _add_days(today, n[0]), 2 + n[1]
                if unit in ("week", "weeks"):
                    return _add_days(today, 7 * n[0]), 2 + n[1]
        mo = _index(months, at(0))
        if mo >= 0:
            d = _day_number(toks, i + 1, lang)
            if d:
                iso = _day_of_month(today, mo + 1, d[0])
                return (iso, 1 + d[1]) if iso else None
        the = 1 if at(0) == "the" else 0
        d = _day_number(toks, i + the, lang)
        if d:
            used = the + d[1]
            if at(used) == "of" and _index(months, at(used + 1)) >= 0:
                iso = _day_of_month(today, _index(months, at(used + 1)) + 1, d[0])
                return (iso, used + 2) if iso else None
            ordinal = re.search(r"(st|nd|rd|th)$", toks[i + the].norm) is not None
            if ordinal and (the or used == 1):
                iso = _day_of_any_month(today, d[0])
                return (iso, used) if iso else None
        return None

    if at(0) == "hoy":
        return today, 1
    if at(0) == "esta" and at(1) in ("noche", "tarde"):
        return today, 2
    if (at(0), at(1)) == ("pasado", "manana"):
        return _add_days(today, 2), 2
    if at(0) == "manana":
        return _add_days(today, 1), 1
    if (at(0), at(1), at(2)) == ("la", "proxima", "semana"):
        return _next_weekday(today, 0), 3
    if (at(0), at(1), at(2), at(3)) == ("la", "semana", "que", "viene"):
        return _next_weekday(today, 0), 4
    if (at(0), at(1)) == ("proxima", "semana"):
        return _next_weekday(today, 0), 2
    if at(0) == "en":
        n = number(toks, i + 1, lang)
        if n:
            unit = at(1 + n[1])
            if unit in ("dia", "dias"):
                return _add_days(today, n[0]), 2 + n[1]
            if unit in ("semana", "semanas"):
                return _add_days(today, 7 * n[0]), 2 + n[1]
    mod = 1 if at(0) in ("proximo", "este") else 0
    wd = _index(weekdays, at(mod))
    if wd >= 0:
        after = 2 if (at(mod + 1), at(mod + 2)) == ("que", "viene") else 0
        return _next_weekday(today, wd), mod + 1 + after
    d = _day_number(toks, i, lang)
    if d:
        if at(d[1]) == "de" and _index(months, at(d[1] + 1)) >= 0:
            iso = _day_of_month(today, _index(months, at(d[1] + 1)) + 1, d[0])
            return (iso, d[1] + 2) if iso else None
        # "el 30": only straight after "el" (the caller's prefix), never a bare number.
        if i > 0 and toks[i - 1].norm == "el":
            iso = _day_of_any_month(today, d[0])
            return (iso, d[1]) if iso else None
    return None


def _hhmm(h: int, m: int) -> str | None:
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return f"{h:02d}:{m:02d}"


def _clock(toks: list[Tok], i: int, lang: Lang) -> tuple[int, int, int] | None:
    t = _at(toks, i) or ""
    hm = re.fullmatch(r"(\d{1,2}):(\d{2})", t)
    if hm:
        return int(hm.group(1)), int(hm.group(2)), 1
    if t in ("a", "an"):
        return None  # "at a …" is not one o'clock
    n = number(toks, i, lang)
    if not n or n[0] > 23:
        return None
    return n[0], 0, n[1]


def _guess_hour(h: int) -> int:
    """Hours said without am/pm: 1-6 mean afternoon, 7-11 morning (task times, not alarms)."""
    return h + 12 if 1 <= h <= 6 else h


def time_piece(toks: list[Tok], i: int, lang: Lang) -> tuple[str, int] | None:
    def at(k: int) -> str | None:
        return _at(toks, i + k)

    if lang == "en":
        lead0 = 1 if at(0) == "at" else 0
        if at(lead0) in ("noon", "midday"):
            return "12:00", lead0 + 1
        if at(lead0) == "midnight":
            return "00:00", lead0 + 1
        c = _clock(toks, i + lead0, lang)
        if not c:
            return None
        h, m, used = c
        used += lead0
        q = at(used)
        q3 = " ".join(w or "" for w in (at(used), at(used + 1), at(used + 2)))
        pm: bool | None = None
        if q in ("am", "pm"):
            pm = q == "pm"
            used += 1
        elif q3 == "in the morning":
            pm = False
            used += 3
        elif q3 in ("in the afternoon", "in the evening"):
            pm = True
            used += 3
        elif q == "at" and at(used + 1) == "night":
            pm = True
            used += 2
        elif q == "oclock":
            used += 1
        if not lead0 and pm is None:
            return None  # a bare number is not a time
        if h > 12 and pm is not None:
            return None
        if pm is True and h < 12:
            h += 12
        elif pm is False and h == 12:
            h = 0
        elif pm is None and h <= 12:
            h = _guess_hour(h)
        s = _hhmm(h, m)
        return (s, used) if s else None

    if (at(0), at(1)) in (("al", "mediodia"), ("a", "mediodia")):
        return "12:00", 2
    if (at(0), at(1)) == ("a", "medianoche"):
        return "00:00", 2
    lead0 = 2 if at(0) == "a" and at(1) in ("las", "la") else 0
    c = _clock(toks, i + lead0, lang)
    if not c:
        return None
    h, m, used = c
    used += lead0
    if (at(used), at(used + 1)) == ("y", "media"):
        m, used = 30, used + 2
    elif (at(used), at(used + 1)) == ("y", "cuarto"):
        m, used = 15, used + 2
    pm = None
    q = " ".join(w or "" for w in (at(used), at(used + 1), at(used + 2)))
    if q == "de la manana":
        pm, used = False, used + 3
    elif q in ("de la tarde", "de la noche"):
        pm, used = True, used + 3
    elif at(used) in ("am", "pm"):
        pm, used = at(used) == "pm", used + 1
    elif (at(used), at(used + 1)) == ("en", "punto"):
        used += 2
    if not lead0 and pm is None:
        return None
    if h > 12 and pm is not None:
        return None
    if pm is True and h < 12:
        h += 12
    elif h == 12 and (pm is False or q == "de la noche"):
        h = 0  # "12 de la mañana" / "12 de la noche" = midnight
    elif pm is None and h <= 12:
        h = _guess_hour(h)
    s = _hhmm(h, m)
    return (s, used) if s else None


def parse_when(toks: list[Tok], today: str, lang: Lang) -> When | None:
    """All of `toks` as one date and/or time expression, in either order."""
    out = When()
    i = 0
    while i < len(toks):
        d = date_piece(toks, i, today, lang) if out.date is None else None
        if d:
            out.date = d[0]
            i += d[1]
            continue
        t = time_piece(toks, i, lang) if out.time is None else None
        if t:
            out.time = t[0]
            i += t[1]
            continue
        return None
    if out.date is None and out.time is None:
        return None
    if out.time is not None and out.date is None:
        out.date = today
    return out


def trailing_when(toks: list[Tok], today: str, lang: Lang) -> tuple[list[Tok], When] | None:
    for start in range(1, len(toks)):
        when = parse_when(toks[start:], today, lang)
        if when:
            return toks[:start], when
    return None


def parse_duration(toks: list[Tok], lang: Lang) -> int | None:
    """Minutes for all of `toks` ("20 minutes", "an hour and a half", "media hora")."""
    i = lead(toks, 0, GRAMMAR[lang].duration_prefix)
    rest = [t.norm for t in toks[i:]]
    s = " ".join(rest)
    if lang == "en":
        if s in ("half an hour", "a half hour"):
            return 30
        if s in ("an hour and a half", "one and a half hours"):
            return 90
    else:
        if s == "media hora":
            return 30
        if s in ("una hora y media", "hora y media"):
            return 90
    n = number(toks, i, lang)
    if not n:
        return None
    unit = rest[n[1]] if n[1] < len(rest) else ""
    extra = " ".join(rest[n[1] + 1 :])
    half = extra == ("and a half" if lang == "en" else "y media")
    if extra and not half:
        return None
    if re.fullmatch(r"minute|minutes|min|mins|minuto|minutos", unit):
        minutes = n[0]
    elif re.fullmatch(r"hour|hours|hora|horas", unit):
        minutes = n[0] * 60 + (30 if half else 0)
    else:
        return None
    if half and not unit.startswith("h"):
        return None
    return minutes if 1 <= minutes <= 1440 else None


def trailing_duration(toks: list[Tok], lang: Lang) -> tuple[list[Tok], int] | None:
    for start in range(1, len(toks)):
        m = parse_duration(toks[start:], lang)
        if m is not None:
            return toks[:start], m
    return None


# -- commands -----------------------------------------------------------------------------------


def _strip_connectors(toks: list[Tok], lang: Lang) -> list[Tok]:
    out = list(toks)
    while len(out) > 1 and out[-1].norm in GRAMMAR[lang].connectors:
        out.pop()
    return out


def _quest_name(toks: list[Tok], lang: Lang) -> str | None:
    out = _strip_connectors(toks, lang)
    while len(out) > 1 and out[0].norm in GRAMMAR[lang].articles:
        out = out[1:]
    s = " ".join(t.raw for t in out)[:120]
    return s or None


def _title(toks: list[Tok], lang: Lang) -> str:
    s = " ".join(t.raw for t in _strip_connectors(toks, lang))[:120]
    return s[:1].upper() + s[1:]


def _parse_in(toks: list[Tok], today: str, lang: Lang) -> dict | None:
    g = GRAMMAR[lang]
    if whole(toks, g.whats_next):
        return {"intent": "whats_next", "lang": lang}
    if whole(toks, g.confirm):
        return {"intent": "confirm", "lang": lang}
    if whole(toks, g.cancel):
        return {"intent": "cancel", "lang": lang}

    n = lead(toks, 0, g.create)
    if n > 0:
        for group in g.create_filler:
            n += lead(toks, n, group)
        rest = toks[n:]
        if not rest:
            return None
        split = trailing_when(rest, today, lang)
        cmd: dict = {"intent": "create", "lang": lang}
        cmd["title"] = _title(split[0] if split else rest, lang)
        if split and split[1].date:
            cmd["date"] = split[1].date
        if split and split[1].time:
            cmd["time"] = split[1].time
        return cmd

    snooze = lead(toks, 0, g.snooze_only)
    defer = lead(toks, 0, g.defer_only)
    either = lead(toks, 0, g.either)
    verb = max(snooze, defer, either)
    if verb > 0:
        rest = toks[verb:]
        if not rest:
            return None
        dur = trailing_duration(rest, lang)
        if dur:
            return _drop_none(
                {"intent": "snooze", "lang": lang, "quest": _quest_name(dur[0], lang)}
            ) | {"minutes": dur[1]}
        when = trailing_when(rest, today, lang)
        if when:
            return _drop_none(
                {
                    "intent": "defer",
                    "lang": lang,
                    "quest": _quest_name(when[0], lang),
                    "date": when[1].date,
                }
            )
        intent = "defer" if defer == verb else "snooze"
        return _drop_none({"intent": intent, "lang": lang, "quest": _quest_name(rest, lang)})

    n = lead(toks, 0, g.complete)
    if n > 0:
        rest = toks[n:]
        t = tail(rest, g.complete_tail)
        if t > 0 and len(rest) > t:
            rest = rest[: len(rest) - t]
        if not rest:
            return None
        return _drop_none({"intent": "complete", "lang": lang, "quest": _quest_name(rest, lang)})
    return None


def _drop_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def parse_command(text: str, today: date | str, hint: Lang = "en") -> VoiceCommand:
    """Parse one utterance. `today` is the local reference day."""
    day = today.isoformat() if isinstance(today, date) else today
    langs: tuple[Lang, Lang] = ("es", "en") if hint == "es" else ("en", "es")
    for lang in langs:
        g = GRAMMAR[lang]
        toks = tokenize(text)
        toks = toks[lead(toks, 0, g.polite) :]
        t = tail(toks, g.polite)
        if t > 0 and len(toks) > t:
            toks = toks[: len(toks) - t]
        cmd = _parse_in(toks, day, lang)
        if cmd:
            return VoiceCommand.model_validate(cmd)
    return VoiceCommand.model_validate({"intent": "unknown", "lang": hint})
