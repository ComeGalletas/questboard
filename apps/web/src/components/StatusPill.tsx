"use client";

import { useNow, useRunnerState } from "@/lib/hooks";
import { runnerStatus, statusLabel } from "@/lib/runner-status";

export function StatusPill() {
  const state = useRunnerState();
  const now = useNow();
  const status = runnerStatus(state?.heartbeat_at, now);
  return (
    <span className="pill" data-kind={status.kind} role="status">
      {statusLabel(status)}
    </span>
  );
}
