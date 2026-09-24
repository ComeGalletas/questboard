// Quest actions: the only way the app changes a quest's status. Pure code (P2).
// Returns the DB patch plus the persona trigger the action fires.

import type { PersonaLine, Quest } from "@questboard/schema";
import { awardedXp, type Finish } from "./xp.ts";
import { endOfLocalDay, isoDate } from "./dates.ts";

export type Trigger = PersonaLine["trigger"];

export type QuestAction =
  | { kind: "start" }
  | { kind: "complete"; actualMin: number }
  | { kind: "partial"; actualMin: number }
  | { kind: "snooze"; minutes: number }
  | { kind: "defer"; to: string }
  | { kind: "skip" };

export type QuestPatch = Partial<
  Pick<
    Quest,
    | "status"
    | "started_at"
    | "completed_at"
    | "snoozed_until"
    | "scheduled_for"
    | "actual_min"
    | "xp_awarded"
  >
>;

export type ActionResult =
  | { ok: true; patch: QuestPatch; trigger: Trigger; finish?: Finish }
  | { ok: false; reason: string };

const ACTIVE: ReadonlySet<Quest["status"]> = new Set([
  "open",
  "in_progress",
  "snoozed",
  "deferred",
  "overdue",
]);

const EARLY_MS = 24 * 3_600_000;

/** How a completion counts against the deadline (or, without one, the scheduled day). */
export function finishTiming(
  q: Pick<Quest, "deadline" | "scheduled_for">,
  now: Date,
): Exclude<Finish, "partial"> {
  const due = q.deadline
    ? new Date(q.deadline)
    : q.scheduled_for
      ? endOfLocalDay(q.scheduled_for)
      : null;
  if (!due) return "on_time";
  if (now.getTime() > due.getTime()) return "late";
  if (q.deadline) return due.getTime() - now.getTime() >= EARLY_MS ? "early" : "on_time";
  return q.scheduled_for && isoDate(now) < q.scheduled_for ? "early" : "on_time";
}

export function applyAction(quest: Quest, action: QuestAction, now: Date): ActionResult {
  if (!ACTIVE.has(quest.status)) {
    return { ok: false, reason: `quest is ${quest.status}` };
  }
  const at = now.toISOString();
  switch (action.kind) {
    case "start":
      if (quest.status === "in_progress") return { ok: false, reason: "already started" };
      return {
        ok: true,
        patch: { status: "in_progress", started_at: at, snoozed_until: null },
        trigger: "started",
      };
    case "complete":
    case "partial": {
      if (!(action.actualMin >= 0)) return { ok: false, reason: "actual time must be >= 0" };
      const finish = action.kind === "partial" ? "partial" : finishTiming(quest, now);
      const trigger: Trigger = finish === "partial" ? "partial" : `completed_${finish}`;
      return {
        ok: true,
        finish,
        trigger,
        patch: {
          status: action.kind === "partial" ? "partial" : "done",
          completed_at: at,
          snoozed_until: null,
          actual_min: Math.round(action.actualMin),
          xp_awarded: awardedXp(quest.xp, finish),
        },
      };
    }
    case "snooze":
      if (!(action.minutes > 0)) return { ok: false, reason: "snooze must be > 0 min" };
      return {
        ok: true,
        trigger: "snoozed",
        patch: {
          status: "snoozed",
          snoozed_until: new Date(now.getTime() + action.minutes * 60_000).toISOString(),
        },
      };
    case "defer":
      if (!/^\d{4}-\d{2}-\d{2}$/.test(action.to) || action.to <= isoDate(now)) {
        return { ok: false, reason: "defer needs a future date" };
      }
      return {
        ok: true,
        trigger: "deferred",
        patch: { status: "deferred", scheduled_for: action.to, snoozed_until: null },
      };
    case "skip":
      return { ok: true, trigger: "skipped", patch: { status: "skipped", snoozed_until: null } };
  }
}
