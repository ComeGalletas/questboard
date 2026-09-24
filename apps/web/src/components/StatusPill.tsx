"use client";

import { useLog } from "@/data/log";
import { useNow } from "@/lib/hooks";
import { runnerStatus, statusLabel } from "@/lib/runner-status";

export function StatusPill() {
  const { runner, store } = useLog();
  const now = useNow();
  if (store.kind === "demo") {
    return (
      <span className="pill" data-kind="demo" role="status">
        Demo mode · local data
      </span>
    );
  }
  const status = runnerStatus(runner?.heartbeat_at, now);
  return (
    <span className="pill" data-kind={status.kind} role="status">
      {statusLabel(status)}
    </span>
  );
}
