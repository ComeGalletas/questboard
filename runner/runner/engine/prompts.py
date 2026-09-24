"""Prompt assembly for daily_am. The system prompt is stable across days (cache-friendly);
everything that changes goes in the user prompt as sorted JSON. Prefer diffs over
regeneration: the model sees the current log and proposes changes to it."""

from __future__ import annotations

import json
from typing import Any

from runner.engine.packs import Pack
from runner.engine.validators import BOARD_TRIGGERS, QUEST_TRIGGERS

SYSTEM_TEMPLATE = """You are the planning author for Questboard, a single-user RPG quest board
for real life. Personas hand out quests and react to what the user does. You write today's
content; the app performs it later from a cache. You never act: you propose changes the user
accepts or rejects.

Return one JSON object with:
1. diff.ops: changes to the quest log.
   - add: a new quest (cadence daily is for today; weekly/monthly for the current period).
   - update: change an open quest (title, notes, persona, estimate_min, scheduled_for, priority).
   - drop: remove an open quest that no longer makes sense.
   Every op needs a short reason. Propose few, high-value changes; an empty ops list is fine.
   Rules:
   - Today's daily plan (open daily quests + adds - drops) must fit the capacity in minutes.
   - Never add utilities or subscription quests and never set or change deadlines: bills and
     dates come only from the user's own records.
   - A quest carried 3 times should be split (drop it, add 2-3 smaller quests) or dropped.
   - Use goals and recent outcomes; respect each persona's categories.
2. quest_lines: dialogue for every quest on today's daily board, including your adds.
   - quest is the quest id, or new:N for the N-th add in diff.ops (counting adds only, from 0).
   - persona is the quest's persona; write in that persona's voice.
   - For each of these triggers write 2 lines (variant 1 and 2): {quest_triggers}.
   - condition is "any" unless the line only fits a mood: pleased, neutral or concerned.
3. board_lines: 2 lines per board trigger ({board_triggers}) for each persona with quests today.

Dialogue rules: at most 280 characters, second person, in character, kind but honest. You may use
the placeholders {{time_left}} {{streak}} {{days_carried}} {{actual_vs_estimate}} {{next_quest}}
(the app fills them). Never include personal data: no names of real people, emails, phone
numbers, addresses, account or ID numbers, amounts of money or links. Tokens like PERSON_3 or
ORG_2 are pseudonyms; you may keep them as they are but never guess what they stand for.

Personas:
{personas}"""


def _persona_section(packs: list[Pack]) -> str:
    return "\n\n".join(
        f"## {p.manifest.name} (slug {p.slug}; intensity {p.manifest.intensity}; "
        f"owns {', '.join(c.value for c in p.manifest.owns) or 'nothing'})\n{p.voice}"
        for p in packs
    )


def system_prompt(packs: list[Pack]) -> str:
    personas = _persona_section(packs)
    return SYSTEM_TEMPLATE.format(
        quest_triggers=", ".join(QUEST_TRIGGERS),
        board_triggers=", ".join(BOARD_TRIGGERS),
        personas=personas,
    )


def user_prompt(context: dict[str, Any]) -> str:
    return "Current state (JSON). Propose today's diff and dialogue.\n\n" + json.dumps(
        context, sort_keys=True, indent=1, default=str
    )


PERIOD_TEMPLATE = """You are the planning author for Questboard, a single-user RPG quest board
for real life. Today you plan the {cadence} quests for the period in the state below. You never
act: you propose changes the user accepts or rejects.

Return a QuestDiff (ops + optional summary):
- add {cadence} quests for the period (scheduled_for = period start) that move the goals forward;
- or break an open {cadence} quest into {sub} sub-quests: set parent_id to that quest's id and
  schedule each inside the period{sub_rule}. Keep the parent open: it tracks the whole;
  lower its estimate_min if the sub-quests now carry the work;
- update or drop open {cadence} quests that no longer fit (carries show what keeps slipping).
Rules: the {cadence} total must fit budget_min; never add utilities or subscription quests and
never set or change deadlines; keep titles short, concrete and free of personal data
(no names of real people, emails, phone or ID numbers, amounts of money, links).
Give every op a one-sentence reason. Few, high-value ops; an empty list is fine.

Personas:
{personas}"""


def period_system_prompt(packs: list[Pack], cadence: str) -> str:
    sub = "daily" if cadence == "weekly" else "weekly"
    return PERIOD_TEMPLATE.format(
        cadence=cadence,
        sub=sub,
        sub_rule=" (weekly sub-quests on a Monday)" if sub == "weekly" else "",
        personas=_persona_section(packs),
    )
