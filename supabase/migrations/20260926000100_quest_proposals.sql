-- Phase 2: model-proposed quest changes wait here until the user accepts or rejects them
-- (invariant 3). Shape = packages/schema/schemas/quest_proposal.schema.json.

create table public.quest_proposals (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  run_id     uuid references public.llm_runs (id) on delete set null,
  op         text not null check (op in ('add', 'update', 'drop')),
  quest_id   uuid references public.quests (id) on delete cascade,
  payload    jsonb not null check (payload ->> 'op' = op),
  lines      jsonb not null default '[]' check (jsonb_typeof(lines) = 'array'),
  status     text not null default 'pending'
             check (status in ('pending', 'accepted', 'rejected', 'superseded')),
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  check ((op = 'add') = (quest_id is null)),
  check ((status = 'pending') = (decided_at is null) or status = 'superseded')
);

create index quest_proposals_pending_idx on public.quest_proposals (user_id, created_at)
  where status = 'pending';

alter table public.quest_proposals enable row level security;
revoke all on public.quest_proposals from anon;
grant select, insert, update, delete on public.quest_proposals to authenticated;
create policy owner_all on public.quest_proposals for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

alter publication supabase_realtime add table public.quest_proposals;
