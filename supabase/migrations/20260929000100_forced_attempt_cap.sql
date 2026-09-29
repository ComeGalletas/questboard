-- "Suggest quests now": forced manual re-runs (llm_runs.forced) may go past the 3-attempt cap,
-- up to 10 attempts per (job, slot, date). Scheduled and plain manual runs stay at 3.
-- Shape = packages/schema/schemas/llm_run.schema.json (attempt).

alter table public.llm_runs drop constraint llm_runs_attempt_check;
alter table public.llm_runs add constraint llm_runs_attempt_check
  check (attempt between 1 and 10 and (forced or attempt <= 3));
