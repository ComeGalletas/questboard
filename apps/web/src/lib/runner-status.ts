// Runner status for the header pill. Pure code (P2): no network, no model.

/** The runner ticks every 5 min; three missed ticks means it is offline. */
export const OFFLINE_AFTER_MS = 15 * 60 * 1000;

export type RunnerStatus =
  { kind: "online"; lastSeenMs: number } | { kind: "offline"; lastSeenMs: number | null };

export function runnerStatus(heartbeatAt: string | null | undefined, now: Date): RunnerStatus {
  if (!heartbeatAt) return { kind: "offline", lastSeenMs: null };
  const seen = Date.parse(heartbeatAt);
  if (Number.isNaN(seen)) return { kind: "offline", lastSeenMs: null };
  const age = Math.max(0, now.getTime() - seen);
  return age <= OFFLINE_AFTER_MS
    ? { kind: "online", lastSeenMs: age }
    : { kind: "offline", lastSeenMs: age };
}

export function formatAge(ms: number): string {
  const min = Math.floor(ms / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const h = Math.floor(min / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.floor(h / 24)} d ago`;
}

export function statusLabel(status: RunnerStatus): string {
  if (status.kind === "online") return "Runner online";
  if (status.lastSeenMs === null) return "Runner offline · never seen";
  return `Runner offline · seen ${formatAge(status.lastSeenMs)}`;
}
