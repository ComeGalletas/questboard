-- Milestone celebrations (Phase 3). The app detects milestones in code (P2); personas say a
-- milestone line. Milestone ids are a registry in packages/schema (common MilestoneId), stored
-- here as plain text so adding a milestone needs no migration.
-- Shapes: packages/schema/schemas/{persona_line,milestone_reached}.schema.json.

-- One trigger for every milestone; `milestone` says which (null = a generic line).
alter table public.persona_lines
  drop constraint persona_lines_trigger_check,
  add constraint persona_lines_trigger_check check (trigger in (
    'assigned', 'reminder_am', 'reminder_mid', 'reminder_pm', 'started',
    'completed_early', 'completed_on_time', 'completed_late', 'partial', 'snoozed',
    'deferred', 'skipped', 'forgotten', 'overdue_1d', 'overdue_3d', 'overdue_7d',
    'carried_over', 'abandoned', 'all_done', 'half_by_noon', 'nothing_by_15',
    'over_capacity', 'milestone')),
  add column milestone text check (milestone ~ '^[a-z][a-z0-9_]{1,31}$'),
  add constraint persona_lines_milestone_only_for_milestones
    check (milestone is null or trigger = 'milestone');

-- Each milestone is celebrated once, wherever the app is open first.
create table public.milestones_reached (
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  key        text not null check (key ~ '^[a-z0-9_:.-]{1,120}$'),
  milestone  text not null check (milestone ~ '^[a-z][a-z0-9_]{1,31}$'),
  label      text not null check (char_length(label) between 1 and 80),
  reached_at timestamptz not null default now(),
  primary key (user_id, key)
);

alter table public.milestones_reached enable row level security;
revoke all on public.milestones_reached from anon;
grant select, insert, update, delete on public.milestones_reached to authenticated;
create policy owner_all on public.milestones_reached for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
