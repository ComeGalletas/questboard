# ADR 0002: Forced manual re-runs of an LLM job occurrence

- Status: proposed
- Date: 2026-09-29

Touches the "idempotent per `(job, slot, date)`" guard in CLAUDE.md "Scheduler rules" (not one
of the numbered invariants); recorded because it relaxes a guard.

## Context

The first real tick against the hosted DB ran the catch-up `weekly` and `monthly` jobs. Both
succeeded with an empty QuestDiff, so the user saw nothing, and because any succeeded run makes
an occurrence "already done", `python -m runner trigger weekly` could not retry until the next
Sunday (monthly: the next 1st). The DB enforced the same rule with a unique index on successful
runs.

## Decision

- `python -m runner trigger JOB --force` (manual trigger only; the scheduler raises for any
  other trigger) starts a new attempt for the job's latest occurrence even if it succeeded.
- Such an attempt is stored with `llm_runs.forced = true`. The one-success unique index now
  covers non-forced successes only, so ticks, catch-up and plain manual runs stay idempotent.
- `MAX_ATTEMPTS` (3) still applies, counting every attempt of the occurrence, and the DB check
  `attempt between 1 and 3` enforces it too: after an ordinary success, `--force` gives at most
  two more attempts. Beyond that, wait for the next occurrence.
- Pending proposals from earlier attempts of the same occurrence are superseded before the
  forced attempt runs, so the board never shows two plans for one period.
- If the occurrence has no success yet, `--force` is an ordinary manual run (`forced = false`).

## Consequences

- An empty or poor plan can be retried right away (e.g. after editing goals), at most twice.
- Anything reading "the" run of an occurrence must take the latest success
  (`finished_at` order), as the web app's "proposed nothing" notice does.
- Migration `20260929000000_llm_run_outcome.sql` replaces `llm_runs_one_success_idx`;
  `supabase/tests/assertions.sql` covers both the forced success and the attempt cap.
