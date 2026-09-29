// "Send test notification": which kinds can be tested and the status line while the runner
// answers. Pure code (P2). The web app never holds the VAPID private key, so the send itself is
// a `notify_test` live request that the PC runner answers.

import type { NotifyTestRequest, NotifyTestResult } from "@questboard/schema";
import type { LiveRequest } from "../data/store.ts";

export type NotificationKind = NotifyTestRequest["kind"];

/** Every notification kind (exhaustive against the schema), in picker order. */
export const KIND_LABELS = {
  day_ready: "Day ready",
  day_recap: "Day recap",
  week_ready: "Week ready",
  month_ready: "Month ready",
  quest_due: "Quest due",
  quest_overdue: "Quest overdue",
  capacity_alert: "Capacity alert",
  streak_risk: "Streak at risk",
  persona_speech: "Persona speech",
  runner_stale: "Runner stale",
  live_pending: "Live request pending",
} satisfies Record<NotificationKind, string>;

export const KINDS = Object.keys(KIND_LABELS) as NotificationKind[];

const OUTCOME: Record<NotifyTestResult["devices"][number]["outcome"], string> = {
  sent: "sent",
  removed: "expired endpoint removed",
  failed: "failed",
};

export type NotifyTestState = {
  kind: "waiting" | "done" | "error";
  text: string;
  devices: string[];
};

/** What to say about a notify_test request (null = just sent, nothing read back yet). */
export function notifyTestState(
  req: LiveRequest<NotifyTestResult> | null,
  offline: boolean,
): NotifyTestState {
  if (!req || req.status === "pending" || req.status === "running") {
    return {
      kind: "waiting",
      text: offline
        ? "Waiting for your PC's runner… (it sends when the PC is on)"
        : "Asking your PC's runner to send it…",
      devices: [],
    };
  }
  if (req.status === "cancelled") {
    return {
      kind: "error",
      text: "The request expired before the runner picked it up.",
      devices: [],
    };
  }
  if (req.status === "failed" || !req.result) {
    return { kind: "error", text: `Not sent: ${req.error ?? "unknown error"}.`, devices: [] };
  }
  const { devices } = req.result;
  const sent = devices.filter((d) => d.outcome === "sent").length;
  return {
    kind: sent > 0 ? "done" : "error",
    text: `Test sent to ${sent} of ${devices.length} device${devices.length === 1 ? "" : "s"}.`,
    devices: devices.map(
      (d) => `${d.device}: ${OUTCOME[d.outcome]}${d.error ? ` (${d.error})` : ""}`,
    ),
  };
}
