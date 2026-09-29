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
- [x] Hosted Supabase project (`rhekvhdfrtjuosflhadh`): all migrations pushed, sign-ups off (email provider on), anon role refused on every table. Web app on Vercel (`questboard-lemon.vercel.app`) built against it; sign-in tested in a browser; `runner tick` against it OK. Verified 2026-09-29.
- [x] Web app shell: auth, Today/Week/Month routes, status pill reading `runner_state`. (Static export for Vercel + Tauri; email/password sign-in so iOS stays in the PWA.)
- [x] PWA manifest + iOS install; Web Push registration. (Pending: iPhone test, see "Pending device tests".)
- [x] CI: lint, type-check, schema codegen check, runner tests. (`.github/workflows/ci.yml`: schema freshness + tsc, web lint/test/build, runner ruff/pytest, sanitizer gate, migrations, live Supabase.) All six jobs are required checks on `main` (ruleset "main", 2026-09-29).
- [x] `runner/providers/base.py` + `claude_cli.py` with a fixture-driven test validating a QuestDiff response (first task #4 in PLAN.md).

Done when: log in on PC and phone and see an empty board with a "Runner offline" pill. (PC done 2026-09-29; phone pending.)

### Pending device tests (iPhone, on the hosted app)
- [ ] On-demand test notification first (needed to run the tests below easily): `python -m runner notify-test [kind]` plus a "Send test notification" button in the app (queued to the runner as a live request, since only the runner holds the VAPID key). It sends a real Web Push of any kind to every subscribed device right away, marked as a test, ignoring quiet hours and dedup.
- [ ] Install the PWA from Safari (Share → Add to Home Screen); it opens standalone and stays signed in.
- [ ] Sign in on the phone and see the board with the runner status pill.
- [ ] "Enable notifications on this device" creates a `push_subscriptions` row (needs VAPID keys: `python -m runner vapid`).
- [ ] A real Web Push from the runner arrives on the phone and its deep link opens the right screen.
- [ ] Voice hold-to-speak on iOS (Web Speech where available, typed fallback otherwise) + confirmation card.

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
- [x] Engine: prompt assembly, `daily_am` (QuestDiffs + capacity fit + dialogue bundles), `daily_pm` (accounting + carry-over rules). Proposals wait in `quest_proposals`. "Suggest quests now" (Today/Week/Month button, or `python -m runner trigger JOB --force`) re-runs daily_am/weekly/monthly on demand as a forced manual attempt (up to 10 per occurrence; scheduled runs keep 3); a manual daily_am before 05:30 plans today.
- [ ] Weekly/monthly quests don't turn into daily quests. First real run (2026-09-29): the weekly plan had two weekly quests (gym 300 min, pygame 450 min) and no daily steps. The weekly prompt makes the daily breakdown optional, and the model read the 773-min weekly budget as full; daily sub-quests don't count against that budget in `check_period`. The daily_am prompt never asks for today's share of open weekly/monthly quests. Fix: weekly breaks each weekly quest into daily sub-quests on concrete days (parent_id); daily_am pulls today's share into the daily plan within capacity; finishing sub-quests advances the parent.
- [ ] daily_pm "forgotten" accounting. Today daily_pm only carries unfinished dailies to tomorrow (carries + 1, overdue if past deadline, abandoned after 3 carries unless hard deadline); nothing ever sets `forgotten`, so the personas' `forgotten` lines never fire. Decided 2026-09-29: a daily quest never started by 21:00 is marked forgotten for the day (the `forgotten` line fires), then still carries under the normal rules. `forgotten` is a closed status in the app today, so the app's stats and the carry step must treat it as "forgotten today, open tomorrow". Partial quests close and don't carry (unchanged).
- [x] App: review strip for pending proposals (accept applies the op in code and caches its lines; reject records feedback).
- [x] `persona_lines` selection in the app. (Done in Phase 1.)
- [ ] Tauri shell: dashboard window, tray, start-at-login, sidecar, OS notifications, deep links.
- [x] Notifications v1 (runner): day_ready, day_recap, quest_due, quest_overdue, streak_risk; DB dedup, delivery after quiet hours, 12 h max age; Web Push (VAPID) with dead-endpoint cleanup.
- [x] PWA: service worker + "Enable notifications on this device" (`push_subscriptions`). Pending: real device test (see "Pending device tests"); headless Chromium can't subscribe.
- [ ] PC delivery of notifications (Tauri reads `notifications` over realtime) + sprite state.

## Phase 3 — Calendar, setup assistant, weekly/monthly (week 4)
- [ ] Microsoft 365 / Outlook calendar (read-only, Microsoft Graph) + `outlook_cal.py` (ADR 0002: Outlook first, Google later). Gitignore every local file the adapter writes (token/MSAL caches, Graph response caches, account/tenant config, captured real events); fixtures stay synthetic.
- [x] Setup assistant (P1): chat on /setup -> pending_live_requests -> runner answers between ticks (5 s poll) with a reply + config patch (goals, capacity, quiet hours, timezone, persona order); the user reviews before/after and applies. Seeding first weekly/monthly quests: until config has goals, daily_am/weekly/monthly skip as "not configured" without an `llm_runs` row, so after setup `python -m runner trigger weekly` (or `monthly`, `daily_am`) plans the current period. A slot that already succeeded stays "already done"; `trigger JOB --force` or the board's "Suggest quests" button adds a new attempt (stored with `forced = true`, max 10 attempts per occurrence; ADR 0003). A run that proposes nothing shows "The planner proposed nothing this week" plus its summary on the board.
- [x] `weekly` / `monthly` jobs: carry-over in code, period plans as proposals with sub-quest breakdown (weekly -> daily, monthly -> weekly), budget = 40 % / 25 % of the period's free time.
- [ ] Retro questions and milestone line pools (need new line triggers + a UI; later).
- [x] `pending_live_requests` + "waiting for your PC's runner" state (shown when the runner is offline). `replan` requests ({job}) are answered with a forced planning run through the scheduler (llm_runs + proposals only); the result carries the scheduler's reason and op count.
- [ ] Companion overlay window (frameless, transparent, always-on-top, click-through outside sprite).

## Phase 4 — Email pipeline (weeks 5–6)
- [ ] Outlook mail adapter (read-only, Microsoft Graph, runner only), allow/deny lists, `senders` classification (ADR 0002; Gmail later). Gitignore every local file the adapter writes (mail dumps, Graph caches, token caches, captured real messages); fixtures stay synthetic.
- [x] Sanitizer: Presidio + spaCy es/en NER, custom recognizers (cédula, NIT with check digit, CO phones, Luhn cards, IBAN mod-97, amounts, CO/US addresses, account/reference numbers, OTP codes and passwords), residual pass for leftover numbers/codes, stable salted tokens, reply/signature stripping, 1200-char window + 800-char cap, `log_rows` for `sanitization_log` (written by the mail pipeline). Tokens come from a `Vault` protocol; `MemoryVault` for now.
- [x] Vault: `vault.db` (SQLCipher) + AES-GCM sealed values, master key in the OS keychain (runner via `keyring`; Tauri reads the same entry later), stable tokens across restarts, `rehydrate()` for the PC UI; `python -m runner vault`. Key loss = mapping loss until the encrypted backup (Phase 7).
- [x] Make "Sanitizer release gate" a required check (issue #14): ruleset "main" (active, default branch) requires it plus the other five CI checks, and blocks deletion and force-push. Verified 2026-09-29.
- [ ] Category profiles + extractors in order: ics, utilities, government, delivery, subscription, health, jobs, learning, travel, personal.
- [ ] Quest templates per category; auto-complete by `reference_token`.
- [ ] LLM-proposed bucket; PII output validator.
- [x] Adversarial email fixture suite as CI release gate: `runner/tests/sanitize/fixtures/` (23 es/en cases), own CI job "Sanitizer release gate", required on `main`.

## Phase 5 — Voice (week 7)
- [ ] PC capture with whisper.cpp; mobile Web Speech with clip fallback (P1).
- [x] Grammar parser (es/en): create/complete/snooze/defer/what's next, dates and times; one grammar in TS and Python locked to shared fixtures (ADR 0001: not chrono-node / dateparser).
- [x] Confirmation card before any write (Today board: hold-to-speak via Web Speech where available, or type; Confirm or spoken/typed "confirm").
- [ ] LLM fallback for unparsed utterances. Decided 2026-09-29: the app sends the utterance through the sanitizer as a short-lived `pending_live_requests` row, the runner answers with a P1 diff, and the row is deleted after the answer (transcripts are never persisted). The same sanitized row also carries the clip fallback later.

## Phase 6 — Custom personas, assets, 3D (week 8)
- [x] Pack loader with validation (manifest, fallback lines, sprite frames, size limits); missing frames -> idle; `python -m runner packs`.
- [x] `persona_digest` weekly job with guardrails (voice-only schema, rule-talk + PII check, re-digests only changed `context/`; cached in the runner data dir).
- [ ] Setup assistant drafts a pack from a description.
- [ ] Optional GLB renderer (three.js) with budget check and sprite fallback.
- [x] Effort-calibration table fed back into prompts (+ add-quest hint).

## Phase 7 — Polish and hardening (ongoing)
- [ ] Final sprite sheets, portraits, animation timing.
- [ ] Google adapters (Gmail + Calendar) behind the ingest interface (moved here by ADR 0002).
- [ ] Capacitor wrapper for iOS widgets.
- [ ] Cloud fallback via Supabase cron when runner heartbeat is stale.
- [ ] Encrypted backup/export of config, packs and vault.

## Open questions (decide when reached)
- ~~daily_am cost~~ → fine for now (2026-09-29): one real run with 2 quests used ~49k input / ~38k output tokens (dialogue for 18 triggers x 2 variants per quest). Revisit if cost matters.
- Monthly carry-over cap is 2 (CLAUDE.md only names daily 3 / weekly 2). Change `MAX_CARRIES` if you want otherwise.
- Period budgets (weekly 40 %, monthly 25 % of free time) are guesses; tune `BUDGET_SHARE`.
- ~~Freshness cap meaning~~ → confirmed: LLM jobs wait for ingest data < 2 h old (only with an integration on); manual runs skip it.
- ~~Where proposed QuestDiffs wait~~ → decided: `quest_proposals` table (one row per op, pending/accepted/rejected).
- ~~`push_subscriptions`~~ → added with notifications v1.
- Custom packs live in `personas/` next to the built-ins; the web bundles them at build time. A per-machine packs folder (outside the repo) would also need the assets uploaded to Supabase storage for the phone. Decide when the first custom pack exists.
- ~~`progress` table~~ → decided 2026-09-29: write cached daily rows (stats still computed in code from the quest log; the rows are a cache, not the source).
- ~~`goals` table vs `config.goals`~~ → fine for now (2026-09-29): `config.goals` stays the working source (setup assistant and prompts use it); the `goals` table is unused.
1. ~~Gmail restricted-scope verification~~ → deferred with Google (ADR 0002). New: personal Microsoft account or a work/school tenant (a tenant may need admin consent for `Mail.Read` / `Calendars.Read`).
2. Mobile re-hydration of pseudonyms (default: no).
3. Whisper model size (tiny vs small); measure latency first.
4. `persona_speech` notifications on mobile by default (default: PC only).
