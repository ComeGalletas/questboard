-- daily_pm "forgotten" accounting (decided 2026-09-29): a daily quest never started on its
-- board day gets that day appended to forgotten_on and still carries under the normal rules.
-- Forgotten is an event, not a status, so 'forgotten' leaves the status check (nothing ever
-- set it). Shape = packages/schema/schemas/quest.schema.json.

alter table public.quests add column forgotten_on date[] not null default '{}';

alter table public.quests drop constraint quests_status_check;
alter table public.quests add constraint quests_status_check check (status in (
  'open', 'in_progress', 'done', 'partial', 'snoozed', 'deferred', 'skipped', 'overdue',
  'abandoned'));
