-- Weekly / monthly retro (Phase 3). The weekly (Sunday) and monthly (1st) jobs ask 2-3 questions
-- about the period that ended; the user answers or skips on the Week / Month board; answers go
-- into later planning prompts as the user's own reflection.
-- Shape: packages/schema/schemas/retro.schema.json.

create table public.retros (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  cadence      text not null check (cadence in ('weekly', 'monthly')),
  period_start date not null,
  period_end   date not null check (period_end >= period_start),
  questions    jsonb not null check (jsonb_typeof(questions) = 'array'),
  answers      jsonb check (answers is null or jsonb_typeof(answers) = 'array'),
  status       text not null default 'open' check (status in ('open', 'answered', 'skipped')),
  source       text not null check (source in ('model', 'fallback')),
  answered_at  timestamptz,
  created_at   timestamptz not null default now(),
  unique (user_id, cadence, period_start)
);

alter table public.retros enable row level security;
revoke all on public.retros from anon;
grant select, insert, update, delete on public.retros to authenticated;
create policy owner_all on public.retros for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
