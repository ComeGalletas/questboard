# Questboard

Single-user, self-hosted RPG quest giver for real life. Personas hand out daily / weekly /
monthly quests; an LLM authors content on a schedule and the app performs it from a cache.
Start with [`CLAUDE.md`](CLAUDE.md) (invariants and architecture) and
[`docs/PLAN.md`](docs/PLAN.md) (phases). Progress lives in [`TODO.md`](TODO.md).

## Layout

| Path | What |
|---|---|
| `apps/web` | Next.js app (static export) for the PWA and, later, the Tauri shell |
| `runner` | Python 3.12 runner: scheduler, providers, engine (`uv`) |
| `packages/schema` | JSON Schemas → generated TS + Pydantic (`pnpm schema:gen`) |
| `personas` | Built-in persona packs |
| `supabase` | Migrations, local config, DB tests |

## Local development

Needs Node 22 + pnpm, Python 3.12 via [uv](https://docs.astral.sh/uv/), and Docker for the
local Supabase stack.

```sh
pnpm install
(cd runner && uv sync)

# Database: local Supabase (Postgres + auth + REST + realtime) with all migrations applied.
supabase/tests/live.sh          # starts the stack, creates the test user, runs live tests
pnpm exec supabase status       # URLs and local keys
pnpm db:reset                   # wipe and re-apply migrations

# Web app against the local stack (or try "Try the demo" without any backend).
cd apps/web
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 \
NEXT_PUBLIC_SUPABASE_ANON_KEY=<ANON_KEY from supabase status> pnpm dev
# sign in as me@questboard.test / quest-pass-123 (local test user only)

# Runner (keeps its session in the OS keychain).
cd runner
uv run python -m runner login   # Supabase URL + anon key, then email/password
uv run python -m runner run     # trigger loop; `tick` or `trigger daily_am` for one pass
```

## Persona packs

A pack is a folder in `personas/` (see CLAUDE.md "Persona packs" for the layout). Check one
before use with `(cd runner && uv run python -m runner packs)`: errors reject the pack (missing
sprite, bad manifest, fallback lines missing a trigger); warnings mean it loads degraded (a sheet
with fewer than five frames shows idle for the missing states). Lore in a pack's `context/`
(`.md` / `.txt`) is condensed each Sunday by the `persona_digest` job into a short style guide,
cached on the runner machine, and added to planning prompts. It shapes the voice only.

## Checks

```sh
pnpm schema:check && pnpm typecheck
(cd apps/web && pnpm lint && pnpm test)
(cd runner && uv run ruff check . && uv run pytest)
supabase/tests/run.sh           # migrations on plain Postgres: RLS, constraints, schema drift
supabase/tests/live.sh          # real Supabase stack: auth, RLS, runner jobs end to end
```

## Hosted setup (when ready)

1. Create a Supabase project; in Auth settings turn sign-ups off, keep the email provider on.
2. Create your user in the dashboard (Authentication → Add user).
3. `pnpm exec supabase link --project-ref <ref>` then `pnpm exec supabase db push`.
4. Deploy `apps/web` (e.g. Vercel) with `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
5. On the PC: `python -m runner login` with the same URL and anon key.
6. Finish the setup assistant (/setup) before expecting plans: until config has goals, the
   planning jobs (`daily_am`, `weekly`, `monthly`) skip as "not configured" and leave their slot
   open. Then `uv run python -m runner trigger weekly` (and `monthly`) seeds the current period.

## Re-running a job

Scheduled runs and a plain manual `trigger` succeed at most once per `(job, slot, date)`
(`llm_runs_one_success_idx`). To plan a slot again (e.g. an empty plan, or goals changed), force
a new attempt (or tap "Suggest quests" on the board, which asks the runner to do the same);
pending proposals from the earlier attempts are superseded first (ADR 0003):

```sh
uv run python -m runner trigger weekly --force
```

Forced attempts stop at 10 per occurrence (scheduled runs at 3). Past that, delete its runs in the Supabase SQL editor and trigger again. The occurrence date is the
slot's own day: the Sunday for `weekly`, the 1st for `monthly`, today for `daily_am`
(`slot = 'AM'`).

```sql
delete from public.llm_runs where job = 'weekly' and date = '2026-09-27';
```

Proposals from deleted runs keep their rows (`run_id` becomes null); reject any still pending
on the board so they don't sit next to the new plan.

## Testing notifications on a phone

Real notifications only fire on schedule (and wait out quiet hours), so there is an on-demand
test. Setup once: `uv run python -m runner vapid`, put `QUESTBOARD_VAPID_PRIVATE_KEY` in the
runner's environment and `NEXT_PUBLIC_VAPID_PUBLIC_KEY` in the web build, then on the phone
install the PWA (Safari → Share → Add to Home Screen), open it from the home screen and tap
"Enable notifications on this device".

- **From the app:** pick a kind next to "Send test notification" and tap it. The PC runner
  (which holds the private key) answers within a few seconds while `runner run` is going; until
  then the app shows "Waiting for your PC's runner". The result lists each device.
- **From the PC:**

  ```sh
  uv run python -m runner notify-test            # day_ready
  uv run python -m runner notify-test quest_due  # any notification kind
  ```

The push goes to every subscribed device right away, ignoring quiet hours, dedup and the 12 h
max age. Its title starts with `[Test]`, the payload carries `test: true`, and it deep-links
to the screen that kind would open (a quest kind opens your most urgent open quest), so tapping
it tests the link too. Tests are never written to `notifications`. Each device reports `sent`,
`expired endpoint removed` (the push service dropped it; enable notifications again on it) or
`failed` with the push service's status; endpoints and keys are never printed.
