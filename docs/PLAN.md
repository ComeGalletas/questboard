# Questboard — Build Plan

Consolidated as of 2026-09-24. Single-user, self-hosted, cache-driven RPG quest giver. See `CLAUDE.md` for invariants and conventions.

## Goals

- Daily / weekly / monthly quests from calendar, email, goals and voice, sorted into realistic capacity.
- Personas with pixel-art characters that react in real time from pre-generated dialogue.
- Works on PC (Tauri desktop companion + dashboard) and iPhone (PWA), sharing one DB.
- LLM is a scheduled batch author (Claude API, Claude CLI or local Ollama), never a runtime dependency.
- Low maintenance: Supabase + Vercel + one local runner; minimal dependencies.

## Decisions log (settled)

| Area | Decision |
|---|---|
| Users | Single user. Supabase Auth with sign-ups disabled; RLS kept simple. Multi-user later without model changes. |
| Config | One `config` row (JSON). Editable via settings page or the setup assistant. Code owns schema/prompts/scoring; config owns goals/personas/capacity/toggles. |
| Frontend | Next.js React app, used by Tauri and PWA. |
| Desktop | Tauri; companion overlay + dashboard windows; tray; starts at login; hosts the runner. |
| Mobile | PWA v1; Capacitor later for widgets. Read/act only. |
| LLM providers | `claude-api`, `claude-cli` (`claude -p --output-format json`), `ollama` (schema-constrained). Ordered fallback list per job. |
| Scheduling | Runner on PC, trigger + guard model, priority queue P0 > P1 > P2. |
| Content | Daily refresh generates quest diffs + per-quest persona dialogue bundles; app selects lines by trigger/condition; pools for board-level and milestone lines. |
| Email privacy | Local deterministic pseudonymization (Presidio + custom CO recognizers), encrypted local vault, category profiles, deterministic extractors for money/dates. |
| Personas | Built-ins + custom packs (yaml + system.md + context/ + assets). Sprite required, GLB optional. |
| Voice | Push/hold to talk; whisper.cpp on PC, Web Speech on mobile; deterministic grammar first, LLM fallback second; confirmation card before write. |
| Art | SNES-style pixel art, shared 32-color palette, mockup on the design canvas. |

## Phases

Each phase ends with something usable. Estimates assume part-time work.

### Phase 0 — Foundations (week 1)
- [ ] Monorepo scaffold: `apps/web`, `apps/desktop`, `runner`, `packages/schema`, `personas`, `supabase`.
- [ ] `packages/schema`: JSON Schemas for Quest, QuestDiff, PersonaLine, ExtractedRecord, Config, LLMRun; codegen to TS + Pydantic.
- [ ] Supabase project: migrations for core tables; single-user auth; realtime on `quests`, `persona_lines`, `runner_state`.
- [ ] Web app shell: auth, Today/Week/Month routes, status pill reading `runner_state`.
- [ ] PWA manifest + iOS install; Web Push registration (no sends yet).
- [ ] CI: lint, type-check, schema codegen check, runner tests.

**Done when:** you can log in on PC and phone and see an empty board with a "Runner offline" pill.

### Phase 1 — Manual quests and the board (week 2)
- [ ] Quest CRUD (title, persona, estimate, deadline, priority, XP); complete / partial / snooze / defer / skip with actual-time logging.
- [ ] Capacity bar: free hours (manual for now) × focus factor vs planned effort.
- [ ] Progress: XP, level, streaks, stats (Discipline/Health/Career); all computed in code (P2).
- [ ] Persona panel with mood computed from completion rate; fallback lines from `lines.fallback.json`.
- [ ] Pixel UI kit: panels, bars, dialogue box with typewriter, sprite component (integer scaling), palette tokens.
- [ ] Built-in persona packs (coach, teacher, mom, quartermaster) with placeholder 32×32 sprite sheets.

**Done when:** the app is a usable pixel-art to-do board with reactions, offline, no LLM.

### Phase 2 — Runner, providers, daily cache (week 3)
- [ ] Runner skeleton: trigger loop (tick, start, network-up, manual), guards, lock file, `runner_state` heartbeat, `llm_runs` idempotency + backoff + catch-up.
- [ ] Provider layer: `base.py` interface; `claude_cli.py` first (subprocess, timeout, single-flight), then `ollama.py` (schema format), then `claude_api.py`. Output validation + one retry + fallthrough.
- [ ] Engine: prompt assembly (config, goals, open quests, feedback, outcomes), `daily_am` producing QuestDiffs + capacity fit + dialogue bundles; `daily_pm` doing forgotten/partial/overdue accounting and carry-over rules.
- [ ] `persona_lines` selection in the app: trigger + condition + no-repeat + placeholder fill.
- [ ] Tauri shell: dashboard window, tray, start-at-login, runner as sidecar, OS notifications, deep links.
- [ ] Notifications v1: `day_ready`, `day_recap`, `quest_due`, `quest_overdue`, `streak_risk` with dedup and quiet hours; Web Push to the PWA.

**Done when:** the PC generates today's quests and lines at 05:30 (or on boot), and both devices show them.

### Phase 3 — Calendar, setup assistant, weekly/monthly (week 4)
- [ ] Google OAuth (read-only) + `gcal.py` adapter; events → scheduled quests; free time → capacity.
- [ ] Setup assistant: multi-turn chat (P1) with `save_config` structured output; review screen; re-runnable; patches config as diffs; seeds first weekly/monthly quests.
- [ ] `weekly` and `monthly` jobs with sub-quest breakdown, retro questions, board-level and milestone line pools.
- [ ] `pending_live_requests` + mobile "waiting for PC" state.
- [ ] Companion overlay window: frameless, transparent, always-on-top, click-through outside sprite, speech bubble, quick menu, hide on fullscreen, quiet hours.

**Done when:** a fresh install can be configured by talking to the assistant and runs a full week unattended.

### Phase 4 — Email pipeline (weeks 5–6)
- [ ] Gmail adapter (read-only, runner only), allow/deny lists, `senders` classification with one-time LLM classify + cache.
- [ ] Sanitizer: Presidio pipeline, spaCy es/en, custom recognizers (cédula, NIT, CO phones, Luhn, IBAN, OTP-like), stable salted tokens, quoted-reply/signature stripping, 800-char cap, `sanitization_log`.
- [ ] Vault: SQLCipher, key in OS keychain via Tauri; re-hydration in PC UI only; mobile opt-in flag.
- [ ] Category profiles + extractors, in this order: `ics.py`, `utilities.py`, `government.py`, `delivery.py`, `subscription.py`, `health.py`, `jobs.py`, `learning.py`, `travel.py`, `personal.py`.
- [ ] Quest templates per category with lead times, prep/execute splits, auto-complete on completion signals by `reference_token`.
- [ ] LLM-proposed bucket for unmatched mail; PII output validator.
- [ ] Fixture suite of adversarial emails (es/en, cards, cédulas, OTPs) as a CI release gate.

**Done when:** bills, appointments and invites become quests automatically, and nothing sensitive reaches the DB or a model.

### Phase 5 — Voice (week 7)
- [ ] PC capture (hotkey + button) with whisper.cpp small; mobile hold-to-speak with Web Speech, clip fallback via runner (P1).
- [ ] Grammar parser (es/en) for create/complete/snooze/defer/what's-next; date parsing (chrono-node / dateparser).
- [ ] Confirmation card (title, when, persona, estimate) before any write; spoken "confirm".
- [ ] LLM fallback for unparsed utterances as P1 diffs.

**Done when:** "create task visit grandma next Saturday at ten" works offline on both devices.

### Phase 6 — Custom personas, assets, 3D (week 8)
- [ ] Pack loader with validation (yaml schema, sprite frame count, size limits); missing frames → idle.
- [ ] `persona_digest` weekly job for `context/`; capped digest in daily prompts; guardrails on schema/escalation/quiet hours.
- [ ] Setup assistant can draft a pack from a description.
- [ ] Optional GLB renderer (three.js) in companion and dashboard header; clip names = five states; budget check (≈5 MB / 20k tris) with sprite fallback on battery.
- [ ] Effort-calibration table (actual vs estimate per category) fed back into prompts.

### Phase 7 — Polish and hardening (ongoing)
- [ ] Final sprite sheets (Aseprite), portraits, animation timing.
- [ ] Outlook/Microsoft 365 adapter behind the ingest interface.
- [ ] Capacitor wrapper for iOS widgets (lock-screen "current quest").
- [ ] Cloud fallback: if provider = ollama and no heartbeat in 24 h, optional Claude API run from Supabase cron.
- [ ] Backup/export of config, packs and vault (encrypted).

## Open questions (decide when reached)

1. Gmail restricted-scope verification vs. keeping the app in "testing" mode with your own account only.
2. Whether the mobile app should ever re-hydrate pseudonyms (default: no).
3. Whisper model size on the PC in use (tiny vs small) — measure latency first.
4. Whether `persona_speech` notifications go to mobile by default (default: PC only).

## First tasks for Claude Code

1. Scaffold the monorepo and `packages/schema` with the six core schemas and codegen.
2. Write the Supabase migration for the core tables in `CLAUDE.md`.
3. Build the pixel UI kit and the Today board against mock data.
4. Implement `runner/providers/base.py` + `claude_cli.py` with a fixture-driven test that validates a QuestDiff response.
