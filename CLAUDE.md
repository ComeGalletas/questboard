# CLAUDE.md — Questboard

Single-user, self-hosted "RPG quest giver" for real life. Personas (Coach, Teacher, Mom, Quartermaster, plus custom packs) hand out daily / weekly / monthly quests derived from calendar, email, goals and voice input. An LLM authors content on a schedule; the app performs it in real time from a cache. Read `PLAN.md` for phases and milestones.

## Non-negotiable invariants

1. **The UI never waits on a model.** Every screen renders from the cache in the DB. If the cache is stale, show the status pill and fallback lines; never block.
2. **Priority order is P0 → P1 → P2, always.**
   - P0 = cache update (ingest, quest diffs, persona dialogue bundles). Never blocked by anything.
   - P1 = live LLM requests (setup assistant, re-plans, quest-update review, voice fallback). Queued when no provider is reachable; UI shows "pending".
   - P2 = app reactions (XP, streaks, mood, line selection, notifications). Pure code, instant, offline.
3. **The LLM proposes; it never acts.** No sending mail, no editing calendars. OAuth scopes are read-only. Quests from the model are diffs (add/update/drop) against the existing log, accepted or rejected by the user.
4. **Money and dates enter only through deterministic extractors.** The model may phrase and schedule a bill quest; it may not create one from raw text.
5. **Raw email never leaves the PC.** Gmail ingestion runs in the runner; bodies pass the sanitizer before any storage or prompt. The cloud DB holds pseudonymized data only. The token↔value vault is local, encrypted, never synced.
6. **One schema for all providers and all personas.** Claude API, Claude CLI and Ollama produce the same structured output; every persona (built-in or custom pack) fills the same trigger table. Custom prompts cannot change schema, escalation caps or quiet hours.
7. **Sprite is mandatory, 3D is optional.** Notifications, list rows and low-power mode always use the 2D sprite. A missing 3D model or frame degrades silently to the sprite/idle.
8. **Voice never writes without confirmation.** Parse → show confirmation card → tap or spoken "confirm" → write.

## Architecture

```
[Gmail / Google Calendar]          [iPhone PWA]          [PC: Tauri app]
        │ read-only OAuth                │                     │  overlay + dashboard + runner
        ▼                                └────────┬────────────┘
   Runner (PC, Python) ──► Supabase Postgres ◄────┘  (realtime / polling)
   ├─ ingest adapters        (pseudonymized only)
   ├─ sanitizer + vault (local SQLCipher)
   ├─ category extractors
   ├─ LLM providers: claude-api | claude-cli | ollama
   └─ scheduler: triggers + guards + priority queue
```

- **Frontend:** one React app (Next.js) used by both the Tauri desktop shell and the mobile PWA. Same components, different shells.
- **Desktop shell:** Tauri. Two windows: `companion` (frameless, transparent, always-on-top, click-through except sprite, tray icon) and `dashboard`. Starts at login. Hosts the runner as a sidecar process.
- **Mobile:** PWA (installable on iOS, Web Push). Read/act only; no runner. Upgrade path: Capacitor wrapper for widgets.
- **Backend:** Supabase — Postgres, Auth (single user, sign-ups disabled), realtime, storage. No custom server.
- **Runner:** Python service. Cron-like loop driven by triggers (5-min tick, process start, network up, manual) and guards (see below). Single instance via lock file.

## Repository layout

```
apps/web/          React/Next.js app (dashboard, companion view, PWA manifest, push)
apps/desktop/      Tauri shell (windows, tray, notifications, hotkeys, keychain, sidecar)
runner/            Python: scheduler, providers, ingest, sanitizer, extractors, engine
  runner/providers/    claude_api.py, claude_cli.py, ollama.py, base.py
  runner/ingest/       gcal.py, gmail.py, base.py
  runner/sanitize/     presidio pipeline, recognizers (CO formats), vault.py, profiles/
  runner/extractors/   ics.py, utilities.py, government.py, health.py, delivery.py, subscription.py, jobs.py, learning.py, personal.py, travel.py
  runner/engine/       prompt assembly, schemas, validators, quest templates, persona bundles
  runner/voice/        whisper.cpp wrapper, grammar parser, date parsing (es/en)
packages/schema/   shared JSON schemas + TS/Python types (quests, diffs, persona lines, config)
personas/          built-in packs: coach/ teacher/ mom/ quartermaster/
supabase/          migrations, RLS (single user), pg_cron for cloud-only jobs
docs/              PLAN.md, ADRs
```

## Data model (core tables)

`config` (single row JSON: goals, capacity, quiet_hours, xp_weights, llm.providers[], persona order, integrations), `integrations`, `goals`, `personas`, `quests`, `quest_feedback`, `progress`, `persona_lines` (quest_id, persona, trigger, variant, condition, text, used_at), `llm_runs` (job, slot, date, trigger, provider_used, attempt, status, tokens), `runner_state` (heartbeat, last AM/PM success, lock, provider health), `pending_live_requests`, `senders` (domain → category), `extracted_records`, `sanitization_log` (rule hits and counts, never values), `notifications` (kind, target, persona, dedup key).

Local only (runner): `vault.db` (SQLCipher; key in OS keychain): `pseudonyms(token, kind, value_hash, value_encrypted, first_seen)`.

## Scheduler rules

Jobs: `ingest` (every 30 min, no LLM), `daily_am` (05:30, slot AM 05:00–11:59), `daily_pm` (21:00, slot PM 17:00–23:59), `weekly` (Sun 18:00), `monthly` (1st 08:00), `persona_digest` (weekly; digests `context/` of each pack).

Guards before any LLM job: DB reachable; provider reachable; slot window; idempotent per `(job, slot, date)`; retry backoff 5/15/60 min, max 3; catch-up on boot/reconnect runs only the most recent missed slot; freshness cap 2 h unless manual; Ollama skipped on battery < 30% or high load; single instance.

Provider order is a list in config (default `[claude-cli, ollama, claude-api]`), tried in sequence per job; per-job override allowed. Validate every output against the schema; retry once; then fall through.

## Persona packs

```
personas/<slug>/
  persona.yaml          name, slug, accent, intensity (0–3), quiet_hours, owns: [categories], priority
  system.md             voice and values; escalation style
  context/              lore, sample dialogue, do/don't (digested weekly, capped in prompt)
  assets/sprite.png     sheet, 32×32 frames: idle, talk, happy, concerned, sleep
  assets/portrait.png   16×16
  assets/model.glb      optional; animation clips named as the five states
  lines.fallback.json   static lines per trigger
```

Dialogue triggers every pack must produce per quest: `assigned, reminder(am|mid|pm), started, completed(early|on_time|late), partial, snoozed, deferred, skipped, forgotten, overdue(1d|3d|7d), carried_over, abandoned`, 2–3 variants each, with runtime placeholders `{time_left} {streak} {days_carried} {actual_vs_estimate} {next_quest}`. Plus daily board-level lines: all_done, half_by_noon, nothing_by_15, over_capacity. Mood (pleased/neutral/concerned) is computed in code from completion rate and selects the variant bucket.

Carry-over rules live in code: max 3 carries for daily, 2 for weekly; hard-deadline obligations always carry; 3+ carries → AM refresh may propose a split (as a diff).

## Email pipeline (runner only)

`Gmail → adapter → sender classification → sanitizer (category profile) → extractor → quest template → DB`.

- Allow list on by default; deny list; category drop rules (credentials/OTP, marketing, bank statements/card alerts).
- Sanitizer: Presidio + spaCy `es_core_news_md`/`en_core_web_md`, custom recognizers (cédula, NIT, CO phone, Luhn cards, IBAN, OTP-like codes). Pseudonymize with stable salted-hash tokens (`PERSON_7`, `ORG_3`, `AMOUNT_2`). Strip quoted replies/signatures first; cap body at ~800 chars.
- Category profiles let an extractor read only its fields (utilities: amount, due date; health: appointment time, location, prep instructions) and drop everything else. Financial/health mail with no claiming extractor is dropped.
- Extractor contract: `extract(email) -> ExtractedRecord | None` with `category, entity_token, amount?, due_at?, event_at?, location?, instructions[], reference_token?, confidence`. Regex + templates + `.ics` parsing. Extractors also detect completion signals (receipt, delivered, confirmed) and auto-resolve by `reference_token`.
- Unmatched sanitized mail → LLM-proposed bucket, marked `source: llm-proposed`, always requires accept.
- Output validator rejects any model response containing PII-looking values.
- Re-hydration of tokens happens only in the PC UI; the phone shows sanitized text unless opted in.

## Voice

PC: hotkey/button, whisper.cpp small model. Mobile: hold-to-speak, Web Speech API where available, else clip queued to runner (P1). Grammar (P2, on-device, es/en): `create/add task <title> [date]`, `complete <quest>`, `snooze <quest> [dur]`, `defer <quest> to <day>`, `what's next`. Date parsing via chrono-node (web) / dateparser (runner). Anything else → LLM fallback as a P1 diff.

## Notifications

Kinds: `day_ready, day_recap, week_ready, month_ready, quest_due, quest_overdue, capacity_alert, streak_risk, persona_speech, runner_stale (mobile), live_pending (mobile)`. Each carries `kind, target deep link (questboard://...), persona`. Dedup by `(kind, target, date)`; `persona_speech` rate-limited (default 2/day); respect quiet hours; PC also plays the matching sprite state.

## Visual rules

SNES-style pixel art, single 32-color palette, dark ground `#1b1a2e`, panel `#2a2740`, border `#5a5580`, text `#ede9dc`. Persona accents: Coach `#e0623a`, Teacher `#4a8fd6`, Mom `#e6b84a`, Quartermaster `#7fa08a`. Integer sprite scaling, `image-rendering: pixelated`. Pixel font for headings/dialogue, readable sans for content. Reference mockup: the "Questboard mockup" design canvas (PC dashboard, companion overlay, mobile Today, mobile voice).

## Conventions for Claude Code

- Language: TypeScript (web/desktop UI), Python 3.12 (runner), Rust only inside Tauri glue. Keep dependencies minimal; prefer stdlib and what's already in `package.json` / `pyproject.toml`.
- Shared types come from `packages/schema` (JSON Schema → generated TS + Pydantic). Never hand-duplicate a schema.
- Every provider, ingest adapter and extractor implements its base class and ships with fixture-based tests. The sanitizer test suite (`runner/sanitize/tests/fixtures/`) is a release gate — a failing sanitizer test blocks merge.
- Never log or persist raw email, OAuth tokens, vault values or transcripts. Log rule hits and counts only.
- Never call an LLM from the web app directly; all model traffic goes through the runner's provider layer.
- Prefer diffs over regeneration in every engine prompt; include current state and ask for changes.
- Feature flags in `config`, not env vars, for anything the user should be able to toggle (providers, integrations, 3D, mobile re-hydration).
- Small PRs by phase (see PLAN.md). Write an ADR in `docs/adr/` for any change to an invariant above.
- When unsure about a product decision, check PLAN.md, then ask; do not invent new integrations or personas.
