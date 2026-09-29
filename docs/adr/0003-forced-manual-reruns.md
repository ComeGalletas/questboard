# ADR 0003: Forced manual re-runs of an LLM job occurrence

- Status: proposed
- Date: 2026-09-29

Touches the "idempotent per `(job, slot, date)`" guard in CLAUDE.md "Scheduler rules" (not one
of the numbered invariants); recorded because it relaxes a guard.

## Context

The first real tick against the hosted DB ran the catch-up `weekly` and `monthly` jobs. Both
succeeded with an empty QuestDiff, so the user saw nothing, and because any succeeded run makes
an occurrence "already done", `python -m runner trigger weekly` could not retry until the next
Sunday (monthly: the next 1st). The DB enforced the same rule with a unique index on successful
runs. The only way to reopen a slot was deleting its `llm_runs` rows by hand in SQL.

## Decision

- `python -m runner trigger JOB --force` (manual trigger only; the scheduler raises for any
  other trigger) starts a new attempt for the job's latest occurrence even if it succeeded.
- Such an attempt is stored with `llm_runs.forced = true`. The one-success unique index now
  covers non-forced successes only, so ticks, catch-up and plain manual runs stay idempotent.
- Attempts of an occurrence that already succeeded are capped at `MAX_FORCED_ATTEMPTS` (10)
  instead of `MAX_ATTEMPTS` (3); the DB check is `attempt between 1 and 10 and (forced or
  attempt <= 3)`. The user chose a separate cap so that on-demand re-plans work in practice
  while token cost stays bounded (each run costs roughly 8-50k tokens).
- The web app's "Suggest quests" button (Today/Week/Month) sends a `replan` live request
  (P1); the runner answers it with the same forced manual run. The app never calls a model.
- A manual daily_am asked for before its 05:30 slot plans today, not yesterday.
- Pending proposals from earlier attempts of the same occurrence are superseded before the
  forced attempt runs, so the board never shows two plans for one period.
- If the occurrence has no success yet, `--force` is an ordinary manual run (`forced = false`).

## Consequences

- An empty or poor plan can be retried right away (e.g. after editing goals), up to 9 times
  after the first success.
- Anything reading "the" run of an occurrence must take the latest success
  (`finished_at` order), as the web app's "proposed nothing" notice does.
- Migration `20260929000000_llm_run_outcome.sql` replaces `llm_runs_one_success_idx`;
  `20260929000100_forced_attempt_cap.sql` raises the cap for forced attempts;
  `supabase/tests/assertions.sql` covers the forced success and both caps.
