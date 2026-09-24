-- Phase 2: the scheduler's freshness guard reads when ingest last succeeded.
alter table public.runner_state add column last_ingest_at timestamptz;
