-- Phase 2: Web Push endpoints for the PWA. One row per device/browser; the runner sends to
-- all of them and deletes endpoints the push service reports as gone (404/410).

create table public.push_subscriptions (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null default auth.uid() references auth.users (id) on delete cascade,
  endpoint        text not null check (endpoint ~ '^https://'),
  p256dh          text not null,
  auth            text not null,
  user_agent      text check (char_length(user_agent) <= 300),
  last_success_at timestamptz,
  created_at      timestamptz not null default now(),
  unique (user_id, endpoint)
);

alter table public.push_subscriptions enable row level security;
revoke all on public.push_subscriptions from anon;
grant select, insert, update, delete on public.push_subscriptions to authenticated;
create policy owner_all on public.push_subscriptions for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
