// "Suggest quests now": the status line under the board while a replan request is answered.
// Pure code (P2). The request itself goes through the runner's live queue; the app never
// calls a model.

import type { ReplanResult } from "@questboard/schema";
import type { LiveRequest } from "../data/store.ts";

export type SuggestState = { kind: "waiting" | "done" | "error"; text: string };

/** What to say about a replan request (null = just sent, nothing read back yet). */
export function suggestState(
  req: LiveRequest<ReplanResult> | null,
  offline: boolean,
): SuggestState {
  if (!req || req.status === "pending" || req.status === "running") {
    return {
      kind: "waiting",
      text: offline
        ? "Waiting for your PC's runner… (it plans when the PC is on)"
        : req?.status === "running"
          ? "The planner is working…"
          : "Asking the planner…",
    };
  }
  if (req.status === "done") {
    const n = req.result?.ops_count ?? null;
    if (n === 0) return { kind: "done", text: "The planner proposed nothing new." };
    if (n === null) return { kind: "done", text: "Done. New suggestions are above." };
    return { kind: "done", text: `${n} new suggestion${n === 1 ? "" : "s"} above.` };
  }
  if (req.status === "cancelled") {
    return { kind: "error", text: "The request expired before the runner picked it up." };
  }
  return { kind: "error", text: `The planner couldn't run: ${req.error ?? "unknown error"}.` };
}
