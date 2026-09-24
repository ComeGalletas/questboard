"""Setup assistant (P1): one conversational turn that may propose a config patch.

The assistant replies and may attach `config_patch` (whole top-level keys: timezone, goals,
capacity, quiet_hours, persona_order). The runner only checks that the patched config is
valid; the user reviews and applies it in the app (invariant 3). Providers, integrations,
features and notifications are out of the assistant's reach (invariant 6).
"""

from __future__ import annotations

import json
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError
from questboard_schema.common_schema import JobName
from questboard_schema.config_schema import Config
from questboard_schema.setup_request_schema import SetupRequest
from questboard_schema.setup_turn_schema import SetupTurn

from runner.engine.packs import Pack
from runner.engine.prompts import _persona_section
from runner.providers.base import GenerationRequest, Provider, ProviderResult, run_with_fallback

TIMEOUT_S = 180.0

SYSTEM = """You are the setup assistant of Questboard, a single-user RPG quest board for real
life. Personas (below) hand out daily, weekly and monthly quests. Help the user set up:
- goals: what they want to achieve (id, title, horizon week|month|quarter|year, optional persona);
- capacity: free hours on weekdays and weekends, and a focus factor (0-1, how much of that time
  really goes to quests; 0.6-0.8 is typical);
- quiet_hours: when personas must stay silent (HH:MM start and end, local time);
- timezone (IANA name) and persona_order (who speaks first).

Ask one or two short questions at a time, in the user's language. When you have enough for a
setting, include it in config_patch; each key you send replaces that whole setting, so send the
full goals list, not only new goals. Leave config_patch null when nothing changes. Set done to
true once goals, capacity and quiet hours are settled. You only suggest; the user applies:
never say you have set or saved anything. Say "I suggest" and mention that they can review
and apply the suggested settings below your message.

Current config (JSON):
{config}

Personas:
{personas}"""


def merged_config(config: Config, turn: SetupTurn) -> Config:
    patch = (
        turn.config_patch.model_dump(mode="json", exclude_none=True) if turn.config_patch else {}
    )
    return Config.model_validate({**config.model_dump(mode="json"), **patch})


def check_turn(turn: SetupTurn, config: Config, personas: set[str]) -> list[str]:
    if turn.config_patch is None:
        return []
    problems = []
    p = turn.config_patch
    if p.timezone is not None:
        try:
            ZoneInfo(p.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            problems.append("config_patch.timezone: not an IANA time zone name")
    if p.persona_order is not None:
        unknown = [s.root for s in p.persona_order if s.root not in personas]
        if unknown:
            problems.append("config_patch.persona_order: unknown persona slugs")
    if p.goals is not None:
        ids = [g.id for g in p.goals]
        if len(ids) != len(set(ids)):
            problems.append("config_patch.goals: goal ids must be unique")
        if any(g.persona and g.persona.root not in personas for g in p.goals):
            problems.append("config_patch.goals: unknown persona slug")
    try:
        merged_config(config, turn)
    except ValidationError as exc:
        problems.append(f"config_patch: merged config is invalid ({exc.error_count()} errors)")
    return problems


def setup_turn(
    payload: dict[str, Any], config: Config, packs: list[Pack], providers: list[Provider]
) -> tuple[dict[str, Any], ProviderResult]:
    request = SetupRequest.model_validate(payload)
    transcript = "\n\n".join(f"{m.role.value.upper()}: {m.content}" for m in request.messages)
    gen = GenerationRequest(
        job=JobName.ingest,  # live requests aren't scheduled jobs; job only labels the request
        system=SYSTEM.format(
            config=json.dumps(config.model_dump(mode="json"), indent=1, sort_keys=True),
            personas=_persona_section(packs),
        ),
        prompt=f"Conversation so far:\n\n{transcript}\n\nWrite the assistant's next turn.",
        timeout_s=TIMEOUT_S,
    )
    personas = {p.slug for p in packs}
    result = run_with_fallback(
        providers, gen, SetupTurn, check=lambda t: check_turn(t, config, personas)
    )
    return result.output.model_dump(mode="json"), result
