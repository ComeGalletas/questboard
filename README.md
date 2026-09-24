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
