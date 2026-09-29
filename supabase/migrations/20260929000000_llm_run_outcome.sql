-- What a planning run proposed, and forced manual re-runs.
-- Shape = packages/schema/schemas/llm_run.schema.json (forced, ops_count, summary).
--
-- ops_count / summary: a planning job (daily_am, weekly, monthly) that succeeds with zero ops
-- is shown in the app with the model's summary instead of silence.
-- forced: `python -m runner trigger JOB --force` may add attempts to an occurrence that
-- already succeeded. Only non-forced successes are unique per (job, slot, date), so scheduled
-- and ordinary manual runs stay idempotent; attempts stay capped at 3 by the existing check.

alter table public.llm_runs
  add column forced    boolean not null default false,
  add column ops_count integer check (ops_count >= 0),
  add column summary   text check (char_length(summary) <= 500);

drop index public.llm_runs_one_success_idx;
create unique index llm_runs_one_success_idx on public.llm_runs (user_id, job, slot, date)
  nulls not distinct where status = 'succeeded' and not forced;
