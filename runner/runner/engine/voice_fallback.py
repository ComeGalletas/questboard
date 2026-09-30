"""Voice fallback (P1): an utterance the grammar didn't understand -> a VoiceCommand.

The model only interprets. It returns the same VoiceCommand the grammar produces, and the app
shows it on the confirmation card like any other (invariant 8); nothing is written here.
Transcripts are never kept (CLAUDE.md conventions): the utterance is sanitized with a
throwaway in-memory vault before the prompt, so names, amounts, emails and numbers reach the
model only as tokens (PERSON_1, AMOUNT_1, ...). The tokens in the answer are put back from that
same vault so the card shows the user's own words, and the vault is dropped. An utterance with
a password or one-time code is never sent at all. live.py blanks the stored payload when the
request is answered, and the app deletes the row once it has read the result.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from questboard_schema.common_schema import JobName
from questboard_schema.config_schema import Config
from questboard_schema.voice_command_schema import VoiceCommand
from questboard_schema.voice_fallback_request_schema import VoiceFallbackRequest

from runner.engine.packs import Pack
from runner.engine.validators import pii_problem
from runner.providers.base import GenerationRequest, Provider, ProviderResult, run_with_fallback
from runner.sanitize.pipeline import sanitize
from runner.sanitize.vault import MemoryVault

TIMEOUT_S = 120.0
TOKEN = re.compile(r"\b[A-Z]+_\d+\b")
MAX_AHEAD = timedelta(days=366)
NOT_ALLOWED = {"confirm", "cancel"}  # only meaningful while a card is open; the grammar owns them

SYSTEM = """You interpret one spoken request for Questboard, a personal quest (task) board.
The deterministic grammar could not parse it; you turn it into one command, or "unknown".
You never act: the user sees your command on a confirmation card and confirms or edits it.

Return a VoiceCommand:
- intent "create": the user wants a new task. title = a short task title in the user's
  language (no filler like "remind me to"); date = the day it's for (YYYY-MM-DD), only when a
  day was said or clearly implied; time = HH:MM (24 h), only when a time was said.
- intent "complete" | "snooze" | "defer": about an existing task. quest = how the user named
  it (a few words; the app matches it to the board). complete: minutes = time spent, if said.
  snooze: minutes = how long, if said. defer: date = the new day.
- intent "whats_next": they ask what to do next.
- intent "unknown": anything else (chit-chat, questions, several requests at once).
- lang: "es" or "en", the language of the request.
Resolve relative days against `today` (its weekday is given). Never invent a date or time
that wasn't said. Words like PERSON_1, ORG_2, AMOUNT_1 or EMAIL_1 stand for private details:
copy them exactly where they belong, never guess what they hide."""


def voice_fallback(
    payload: dict[str, Any], config: Config, packs: list[Pack], providers: list[Provider]
) -> tuple[dict[str, Any], ProviderResult | None]:
    request = VoiceFallbackRequest.model_validate(payload)
    lang = request.lang.value
    vault = MemoryVault()
    clean = sanitize(request.utterance, vault, strip=False, lang=lang)
    if clean.drop:  # a password or one-time code: never sent to a model
        return VoiceCommand(intent="unknown", lang=lang).model_dump(
            mode="json", exclude_none=True
        ), None

    today = request.today
    gen = GenerationRequest(
        job=JobName.ingest,  # live requests aren't scheduled jobs; job only labels the request
        system=SYSTEM,
        prompt=json.dumps(
            {
                "today": today.isoformat(),
                "weekday": today.strftime("%A"),
                "lang": lang,
                "request": clean.text,
            },
            ensure_ascii=False,
        ),
        timeout_s=TIMEOUT_S,
    )
    known = set(TOKEN.findall(clean.text))
    result = run_with_fallback(
        providers, gen, VoiceCommand, check=lambda c: check_command(c, today, known)
    )
    return restore(result.output, vault).model_dump(mode="json", exclude_none=True), result


def check_command(cmd: VoiceCommand, today: date, known: set[str]) -> list[str]:
    problems: list[str] = []
    if cmd.intent.value in NOT_ALLOWED:
        problems.append(f"intent {cmd.intent.value} is not allowed here")
    if cmd.intent.value == "create" and not cmd.title:
        problems.append("create needs a title")
    if cmd.intent.value in ("complete", "snooze", "defer") and not cmd.quest:
        problems.append(f"{cmd.intent.value} needs quest")
    if cmd.intent.value == "defer" and cmd.date is None:
        problems.append("defer needs a date")
    if cmd.date is not None and not today - timedelta(days=1) <= cmd.date <= today + MAX_AHEAD:
        problems.append("date is outside the next year")
    for field in ("title", "quest"):
        text = getattr(cmd, field) or ""
        invented = set(TOKEN.findall(text)) - known
        if invented:
            problems.append(f"{field} uses tokens that weren't in the request: {sorted(invented)}")
        problem = pii_problem(text)
        if problem:
            problems.append(f"{field} {problem}")
    return problems


def restore(cmd: VoiceCommand, vault: MemoryVault) -> VoiceCommand:
    """Put the user's words back where the model copied a token (title, quest)."""

    def back(text: str | None) -> str | None:
        if text is None:
            return None
        return TOKEN.sub(lambda m: vault.value_of(m.group(0)) or m.group(0), text)[:120]

    return cmd.model_copy(update={"title": back(cmd.title), "quest": back(cmd.quest)})
