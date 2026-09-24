# ADR 0001: Voice dates parsed by our own grammar, not chrono-node / dateparser

- Status: proposed
- Date: 2026-09-24

Not an invariant change; recorded because CLAUDE.md names chrono-node (web) and dateparser
(runner) for voice dates.

## Context

The Phase 5 milestone is "create task visit grandma next Saturday at ten" working offline on
both devices. With chrono-node 2.x (reference Thursday 2026-09-24):

- "at ten" and "a las diez" are dropped (only "next Saturday" / "próximo sábado" is found);
- "pasado mañana" is read as "mañana";
- "mañana a las 3 de la tarde" becomes 03:00, with "tarde" parsed as a second date.

dateparser's text search is weaker still for embedded phrases, and the two libraries would
disagree with each other, so the phone and the PC could turn the same words into different
dates. Only the web or the runner could have been fixed, never both.

## Decision

A small table-driven es/en grammar, written twice (`apps/web/src/voice/grammar.ts`,
`runner/runner/voice/grammar.py`), both locked to one fixture file
(`packages/schema/fixtures/voice.json`). It covers today / tomorrow / the day after,
weekdays (the next one after today; "next" and "this" mean the same), next week (Monday),
in N days / weeks, day + month, the Nth / el N, and times with digits or words, am/pm,
de la mañana / tarde / noche, noon / mediodía, y media / y cuarto. An hour said without
am/pm reads 1–6 as afternoon and 7–12 as morning / noon.

The output is only shown on the confirmation card, where the user can fix the day or time
before anything is written (invariant 8).

## Consequences

- No new dependencies; the web and the runner agree by construction (CI runs the same
  fixtures on both).
- Phrasing outside the grammar ("the weekend", "end of the month", "in the morning" with no
  hour) yields no date. The card then shows today, and the LLM fallback (P1) can
  take over once it lands.
- New phrases are added to both files and to the fixtures together.
