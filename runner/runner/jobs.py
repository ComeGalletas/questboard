"""Job handlers by name. LLM jobs (daily_am, daily_pm, ...) are added as the engine lands;
a job without a handler is simply not scheduled."""

from __future__ import annotations

from questboard_schema.common_schema import JobName

from runner.scheduler.core import JobContext, JobHandler, JobResult


def ingest(ctx: JobContext) -> JobResult:
    """No ingest adapters yet (gcal in Phase 3, gmail in Phase 4): nothing to pull."""
    return JobResult()


HANDLERS: dict[JobName, JobHandler] = {JobName.ingest: ingest}
