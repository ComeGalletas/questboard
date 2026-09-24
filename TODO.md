# Questboard — TODO

Derived from `CLAUDE.md` and `docs/PLAN.md` (2026-09-24). Check items off as they land.

## Proposed stack

| Layer | Language | Framework / library | Notes |
|---|---|---|---|
| Web UI (dashboard, companion view, PWA) | TypeScript | Next.js (React), Web Push, chrono-node, three.js (optional GLB) | One app for both desktop shell and mobile PWA. Hosted on Vercel. |
| Desktop shell | Rust (glue only) + TypeScript | Tauri | Two windows (`companion`, `dashboard`), tray, start-at-login, keychain, runner as sidecar. |
| Mobile | TypeScript | PWA (installable on iOS); Capacitor later for widgets | Read/act only, no runner. |
| Runner (scheduler, LLM, ingest, voice) | Python 3.12 | Pydantic, Presidio + spaCy (`es_core_news_md`, `en_core_web_md`), SQLCipher, whisper.cpp wrapper, dateparser | Single instance on the PC. All LLM traffic goes through here. |
| LLM providers | Python | `claude-cli` (`claude -p --output-format json`), `ollama` (schema-constrained), `claude-api` | Ordered fallback list in `config`; default `[claude-cli, ollama, claude-api]`. |
| Backend | SQL | Supabase (Postgres, Auth with sign-ups disabled, realtime, storage, pg_cron) | No custom server. Pseudonymized data only. |
| Shared types | JSON Schema | Codegen to TypeScript + Pydantic | Lives in `packages/schema`; never hand-duplicate. |
| Persona packs | YAML + Markdown + PNG (+ optional GLB) | Pack loader with validation | 32x32 sprite sheets, 16x16 portraits. |
| Art | — | Aseprite, SNES-style 32-color palette | Palette and accents defined in `CLAUDE.md`. |

Tooling not named in the docs (confirmed 2026-09-24):
- Monorepo: pnpm workspaces (+ Turborepo if builds get slow).
- Python: `uv` for env/deps, `pytest` for tests, `ruff` for lint/format.
- TS: ESLint + Prettier, `tsc --noEmit` in CI.
- Schema codegen: `json-schema-to-typescript` and `datamodel-code-generator` (Pydantic).

## Housekeeping
- [x] Move `CLAUDE.md` to the repo root and `PLAN.md` to `docs/PLAN.md`.
- [x] `git init`, add `.gitignore` (node, python, tauri, `vault.db`, `.env`).
- [x] Create `docs/adr/` with an ADR template (required for any invariant change).

## Phase 0 — Foundations (week 1)
- [ ] Monorepo scaffold (pnpm workspace, `packages/schema`, `runner` done; `apps/*`, `personas`, `supabase` land with their PRs): `apps/web`, `apps/desktop`, `runner`, `packages/schema`, `personas`, `supabase`, `docs`.
- [x] `packages/schema`: JSON Schemas for Quest, QuestDiff, PersonaLine, ExtractedRecord, Config, LLMRun; codegen to TS + Pydantic; CI check that generated code is fresh.
- [x] Supabase migrations for the 15 core tables; single-user guard + owner-only RLS; realtime on `quests`, `persona_lines`, `runner_state`; tested on local Postgres in CI (`supabase/tests/run.sh`).
- [x] Local Supabase stack (`supabase/tests/live.sh`): migrations, single-user auth, RLS and runner jobs verified end to end; web app verified against it in a browser (sign-in, add, accept proposal, complete, realtime pill).
- [ ] Create the hosted Supabase project, turn sign-ups off (keep the email provider on), `supabase db push` (needs your account; steps in README).
- [x] Web app shell: auth, Today/Week/Month routes, status pill reading `runner_state`. (Static export for Vercel + Tauri; email/password sign-in so iOS stays in the PWA.)
- [x] PWA manifest + iOS install; Web Push registration. (iOS install + real push: test on the phone once hosted.)
- [ ] CI: lint, type-check, schema codegen check, runner tests. (Schema freshness + tsc + runner ruff/pytest done; web lint lands with `apps/web`.)
- [x] `runner/providers/base.py` + `claude_cli.py` with a fixture-driven test validating a QuestDiff response (first task #4 in PLAN.md).

Done when: log in on PC and phone and see an empty board with a "Runner offline" pill.

## Phase 1 — Manual quests and the board (week 2)
- [x] Quest create + complete / partial / snooze / defer / skip with actual-time logging. (Edit/delete of a quest's fields: later, when needed.)
- [x] Capacity bar (manual free hours x focus factor vs planned effort).
- [x] Progress: XP, level, streaks, stats, all computed in code (P2). (`apps/web/src/game/`; UI lands with the board PR.)
- [x] Persona panel with mood from completion rate; `lines.fallback.json`.
- [x] Pixel UI kit: panels, bars, typewriter dialogue box, sprite component, palette tokens.
- [x] Built-in packs (coach, teacher, mom, quartermaster) with placeholder sprites.

## Phase 2 — Runner, providers, daily cache (week 3)
- [x] Runner skeleton: trigger loop, guards, lock file, heartbeat, `llm_runs` idempotency + backoff + catch-up. (Tested against an in-memory DB; Supabase connection next.)
- [x] Providers: `ollama.py`, `claude_api.py`; output validation, one retry, fallthrough. Supabase connection for the runner (signs in as the user; refresh token in the OS keychain).
- [x] Engine: prompt assembly, `daily_am` (QuestDiffs + capacity fit + dialogue bundles), `daily_pm` (accounting + carry-over rules). Proposals wait in `quest_proposals`.
- [x] App: review strip for pending proposals (accept applies the op in code and caches its lines; reject records feedback).
- [x] `persona_lines` selection in the app. (Done in Phase 1.)
- [ ] Tauri shell: dashboard window, tray, start-at-login, sidecar, OS notifications, deep links.
- [x] Notifications v1 (runner): day_ready, day_recap, quest_due, quest_overdue, streak_risk; DB dedup, delivery after quiet hours, 12 h max age; Web Push (VAPID) with dead-endpoint cleanup.
- [x] PWA: service worker + "Enable notifications on this device" (`push_subscriptions`). Needs a real device test: headless Chromium can't subscribe.
- [ ] PC delivery of notifications (Tauri reads `notifications` over realtime) + sprite state.

## Phase 3 — Calendar, setup assistant, weekly/monthly (week 4)
- [ ] Google OAuth (read-only) + `gcal.py`.
- [x] Setup assistant (P1): chat on /setup -> pending_live_requests -> runner answers between ticks (5 s poll) with a reply + config patch (goals, capacity, quiet hours, timezone, persona order); the user reviews before/after and applies. Seeding first weekly/monthly quests: run the weekly/monthly job manually after setup.
- [x] `weekly` / `monthly` jobs: carry-over in code, period plans as proposals with sub-quest breakdown (weekly -> daily, monthly -> weekly), budget = 40 % / 25 % of the period's free time.
- [ ] Retro questions and milestone line pools (need new line triggers + a UI; later).
- [x] `pending_live_requests` + "waiting for your PC's runner" state (shown when the runner is offline).
- [ ] Companion overlay window (frameless, transparent, always-on-top, click-through outside sprite).

## Phase 4 — Email pipeline (weeks 5–6)
- [ ] Gmail adapter (read-only), allow/deny lists, `senders` classification.
- [ ] Sanitizer: Presidio + spaCy es/en, CO recognizers, stable salted tokens, reply/signature stripping, 800-char cap, `sanitization_log`.
- [ ] Vault: SQLCipher, key in OS keychain via Tauri; PC-only re-hydration.
- [ ] Category profiles + extractors in order: ics, utilities, government, delivery, subscription, health, jobs, learning, travel, personal.
- [ ] Quest templates per category; auto-complete by `reference_token`.
- [ ] LLM-proposed bucket; PII output validator.
- [ ] Adversarial email fixture suite as CI release gate.

## Phase 5 — Voice (week 7)
- [ ] PC capture with whisper.cpp; mobile Web Speech with clip fallback (P1).
- [x] Grammar parser (es/en): create/complete/snooze/defer/what's next, dates and times; one grammar in TS and Python locked to shared fixtures (ADR 0001: not chrono-node / dateparser).
- [x] Confirmation card before any write (Today board: hold-to-speak via Web Speech where available, or type; Confirm or spoken/typed "confirm").
- [ ] LLM fallback for unparsed utterances. Open question: it must carry the utterance to the runner, and transcripts are never persisted. Options: send only a sanitized, short-lived request row deleted after the answer, or run the fallback only on the PC where the transcript is already local.

## Phase 6 — Custom personas, assets, 3D (week 8)
- [x] Pack loader with validation (manifest, fallback lines, sprite frames, size limits); missing frames -> idle; `python -m runner packs`.
- [x] `persona_digest` weekly job with guardrails (voice-only schema, rule-talk + PII check, re-digests only changed `context/`; cached in the runner data dir).
- [ ] Setup assistant drafts a pack from a description.
- [ ] Optional GLB renderer (three.js) with budget check and sprite fallback.
- [x] Effort-calibration table fed back into prompts (+ add-quest hint).

## Phase 7 — Polish and hardening (ongoing)
- [ ] Final sprite sheets, portraits, animation timing.
- [ ] Outlook / Microsoft 365 adapter.
- [ ] Capacitor wrapper for iOS widgets.
- [ ] Cloud fallback via Supabase cron when runner heartbeat is stale.
- [ ] Encrypted backup/export of config, packs and vault.

## Open questions (decide when reached)
- daily_am cost: one real run with 2 quests used ~49k input / ~38k output tokens (dialogue for 18 triggers x 2 variants per quest). Consider fewer variants or triggers per run if cost matters.
- Monthly carry-over cap is 2 (CLAUDE.md only names daily 3 / weekly 2). Change `MAX_CARRIES` if you want otherwise.
- Period budgets (weekly 40 %, monthly 25 % of free time) are guesses; tune `BUDGET_SHARE`.
- ~~Freshness cap meaning~~ → confirmed: LLM jobs wait for ingest data < 2 h old (only with an integration on); manual runs skip it.
- ~~Where proposed QuestDiffs wait~~ → decided: `quest_proposals` table (one row per op, pending/accepted/rejected).
- ~~`push_subscriptions`~~ → added with notifications v1.
- Custom packs live in `personas/` next to the built-ins; the web bundles them at build time. A per-machine packs folder (outside the repo) would also need the assets uploaded to Supabase storage for the phone. Decide when the first custom pack exists.
- `progress` table: game stats are computed from the quest log in the app; decide whether the runner/weekly jobs need the cached daily rows before writing them.
- `goals` table vs `config.goals`: pick one source of truth before the setup assistant.
1. Gmail restricted-scope verification vs. "testing" mode with own account.
2. Mobile re-hydration of pseudonyms (default: no).
3. Whisper model size (tiny vs small); measure latency first.
4. `persona_speech` notifications on mobile by default (default: PC only).
