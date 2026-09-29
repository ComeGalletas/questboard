// Parent/sub-quest roll-up. Pure code (P2); the runner computes the same numbers in
// runner/runner/engine/rollup.py.
//
// A weekly (monthly) quest is worked through daily (weekly) sub-quests with parent_id set. The
// parent's estimate_min is the target; each finished sub-quest adds its logged minutes (its
// estimate when none were logged). The parent never closes by itself: it shows progress and,
// once the steps cover the target and none is still open, "ready to turn in". The user turns it
// in with Done, which awards only the XP the steps haven't already earned (see turnInXp).
// Why not auto-complete: the planner adds steps a day at a time, so "all steps done" is true
// every evening long before the week's work is; and closing a quest is the user's call.

import type { Quest } from "@questboard/schema";
import { addDays } from "./dates.ts";

const FINISHED = new Set<Quest["status"]>(["done", "partial"]);
const ACTIVE = new Set<Quest["status"]>(["open", "in_progress", "snoozed", "deferred", "overdue"]);

/** Share of a parent's own XP it always pays when turned in, even if its steps earned more. */
export const TURN_IN_SHARE = 0.2;

export type Rollup = {
  /** Finished steps (done or partial). */
  done: number;
  /** All steps ever planned for this parent, whatever their status. */
  total: number;
  /** Steps still open. */
  open: number;
  doneMin: number;
  targetMin: number;
  /** XP the finished steps have already awarded. */
  earnedXp: number;
  ready: boolean;
};

export function subQuests(parent: Pick<Quest, "id">, quests: Quest[]): Quest[] {
  return quests.filter((q) => q.parent_id === parent.id);
}

/** Progress of a parent through its sub-quests, or null when it has none. */
export function rollup(parent: Quest, quests: Quest[]): Rollup | null {
  const subs = subQuests(parent, quests);
  if (subs.length === 0) return null;
  const finished = subs.filter((q) => FINISHED.has(q.status));
  const doneMin = finished.reduce((sum, q) => sum + (q.actual_min ?? q.estimate_min), 0);
  const open = subs.filter((q) => ACTIVE.has(q.status)).length;
  return {
    done: finished.length,
    total: subs.length,
    open,
    doneMin,
    targetMin: parent.estimate_min,
    earnedXp: finished.reduce((sum, q) => sum + (q.xp_awarded ?? 0), 0),
    ready: open === 0 && doneMin >= parent.estimate_min,
  };
}

/** XP for turning in a parent: what its finish is worth minus what its steps already paid,
 * but never less than a TURN_IN_SHARE bonus of its own XP. */
export function turnInXp(awarded: number, parentXp: number, earnedBySteps: number): number {
  if (earnedBySteps <= 0) return awarded;
  return Math.max(Math.round(parentXp * TURN_IN_SHARE), awarded - earnedBySteps);
}

/** Last day (inclusive) of the board period a quest belongs to. */
export function periodEnd(q: Pick<Quest, "cadence" | "scheduled_for">): string | null {
  if (!q.scheduled_for) return null;
  if (q.cadence === "weekly") return addDays(q.scheduled_for, 6);
  if (q.cadence === "monthly") {
    const [y, m] = q.scheduled_for.split("-").map(Number);
    const last = new Date(y, m, 0).getDate();
    return `${q.scheduled_for.slice(0, 8)}${String(last).padStart(2, "0")}`;
  }
  return q.scheduled_for;
}
