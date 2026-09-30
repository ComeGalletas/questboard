-- PC delivery of notifications (desktop shell, Phase 2). The runner keeps deciding when a
-- notification is released (sent_at, after quiet hours); the shell listens over realtime, shows
-- rows with the 'pc' channel as Windows toasts and stamps pc_shown_at so each shows once.
-- Shape = packages/schema/schemas/notification.schema.json.

alter table public.notifications add column pc_shown_at timestamptz;

-- The shell's startup query: released, PC channel, not shown yet.
create index notifications_pc_pending on public.notifications (sent_at)
  where pc_shown_at is null and sent_at is not null;

alter publication supabase_realtime add table public.notifications;
