-- Phase 1: timestamps and awarded XP for quest actions (complete / partial / snooze / start).
-- Shape = packages/schema/schemas/quest.schema.json.

alter table public.quests
  add column started_at    timestamptz,
  add column completed_at  timestamptz,
  add column snoozed_until timestamptz,
  add column xp_awarded    integer check (xp_awarded >= 0),
  add constraint quests_completed_at_matches_status
    check ((completed_at is not null) = (status in ('done', 'partial')));

create index quests_completed_idx on public.quests (user_id, completed_at)
  where completed_at is not null;
