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
- [ ] Create the hosted Supabase project, turn sign-ups off, apply migrations (needs your account).
- [x] Web app shell: auth, Today/Week/Month routes, status pill reading `runner_state`. (Static export for Vercel + Tauri; email/password sign-in so iOS stays in the PWA.)
- [ ] PWA manifest + iOS install; Web Push registration (no sends yet). (Manifest + placeholder icons done; push registration waits on the `push_subscriptions` decision.)
- [ ] CI: lint, type-check, schema codegen check, runner tests. (Schema freshness + tsc + runner ruff/pytest done; web lint lands with `apps/web`.)
- [x] `runner/providers/base.py` + `claude_cli.py` with a fixture-driven test validating a QuestDiff response (first task #4 in PLAN.md).

Done when: log in on PC and phone and see an empty board with a "Runner offline" pill.

## Phase 1 — Manual quests and the board (week 2)
- [ ] Quest CRUD + complete / partial / snooze / defer / skip with actual-time logging. (Action rules + DB columns done; UI next.)
- [ ] Capacity bar (manual free hours x focus factor vs planned effort). (Calculation done; bar UI next.)
- [x] Progress: XP, level, streaks, stats, all computed in code (P2). (`apps/web/src/game/`; UI lands with the board PR.)
- [ ] Persona panel with mood from completion rate; `lines.fallback.json`. (Mood + line selection + fallback lines done; panel UI next.)
- [ ] Pixel UI kit: panels, bars, typewriter dialogue box, sprite component, palette tokens.
- [x] Built-in packs (coach, teacher, mom, quartermaster) with placeholder sprites.

## Phase 2 — Runner, providers, daily cache (week 3)
- [ ] Runner skeleton: trigger loop, guards, lock file, heartbeat, `llm_runs` idempotency + backoff + catch-up.
- [ ] Providers: `ollama.py`, `claude_api.py`; output validation, one retry, fallthrough.
- [ ] Engine: prompt assembly, `daily_am` (QuestDiffs + capacity fit + dialogue bundles), `daily_pm` (accounting + carry-over rules).
- [ ] `persona_lines` selection in the app.
- [ ] Tauri shell: dashboard window, tray, start-at-login, sidecar, OS notifications, deep links.
- [ ] Notifications v1 with dedup and quiet hours; Web Push to PWA.

## Phase 3 — Calendar, setup assistant, weekly/monthly (week 4)
- [ ] Google OAuth (read-only) + `gcal.py`.
- [ ] Setup assistant (P1) with `save_config` structured output; config patched as diffs.
- [ ] `weekly` / `monthly` jobs; board-level and milestone line pools.
- [ ] `pending_live_requests` + mobile "waiting for PC" state.
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
- [ ] Grammar parser (es/en); chrono-node / dateparser.
- [ ] Confirmation card before any write.
- [ ] LLM fallback for unparsed utterances.

## Phase 6 — Custom personas, assets, 3D (week 8)
- [ ] Pack loader with validation; missing frames -> idle.
- [ ] `persona_digest` weekly job with guardrails.
- [ ] Setup assistant drafts a pack from a description.
- [ ] Optional GLB renderer (three.js) with budget check and sprite fallback.
- [ ] Effort-calibration table fed back into prompts.

## Phase 7 — Polish and hardening (ongoing)
- [ ] Final sprite sheets, portraits, animation timing.
- [ ] Outlook / Microsoft 365 adapter.
- [ ] Capacitor wrapper for iOS widgets.
- [ ] Cloud fallback via Supabase cron when runner heartbeat is stale.
- [ ] Encrypted backup/export of config, packs and vault.

## Open questions (decide when reached)
- Where proposed QuestDiffs wait for accept/reject (no table for them yet; needed in Phase 2).
- `push_subscriptions` table for Web Push (lands with the PWA item).
- `goals` table vs `config.goals`: pick one source of truth before the setup assistant.
1. Gmail restricted-scope verification vs. "testing" mode with own account.
2. Mobile re-hydration of pseudonyms (default: no).
3. Whisper model size (tiny vs small); measure latency first.
4. `persona_speech` notifications on mobile by default (default: PC only).
