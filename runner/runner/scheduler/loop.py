"""Trigger loop: process start, a 5-minute tick, network coming back, and manual runs."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from questboard_schema.llm_run_schema import Trigger

from runner.scheduler.core import DB_DOWN, Decision, Scheduler

TICK_SECONDS = 300
log = logging.getLogger("questboard.runner")


@dataclass
class Loop:
    scheduler: Scheduler
    sleep: Callable[[float], None] = time.sleep
    _db_was_down: bool = field(default=False, init=False)

    def step(self, first: bool = False) -> list[Decision]:
        """One trigger evaluation. The trigger is `start` first, `network_up` after an outage."""
        if first:
            trigger = Trigger.start
        elif self._db_was_down:
            trigger = Trigger.network_up
        else:
            trigger = Trigger.tick
        decisions = self.scheduler.evaluate(trigger)
        self._db_was_down = any(d.reason.startswith(DB_DOWN) for d in decisions)
        for d in decisions:
            # Job names and reasons only: never payloads (CLAUDE.md logging rule).
            log.info("%s %s %s: %s", trigger.value, d.job.value, d.action, d.reason)
        return decisions

    def run_forever(self, ticks: int | None = None) -> None:
        count = 0
        first = True
        while ticks is None or count < ticks:
            try:
                self.step(first=first)
            except Exception as exc:  # noqa: BLE001 - the loop outlives any single failure
                # Class name only: tracebacks and messages can carry data.
                log.error("tick failed: %s", type(exc).__name__)
            first = False
            count += 1
            if ticks is None or count < ticks:
                self.sleep(TICK_SECONDS)
