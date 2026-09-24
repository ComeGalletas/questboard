// Streaks, stats, mood and capacity. Pure code (P2), computed from the quest log.

import type { Config, Quest } from "@questboard/schema";
import { addDays, isoDate } from "./dates.ts";

export type Mood = "pleased" | "neutral" | "concerned";
export type Stat = "discipline" | "health" | "career";

const FINISHED = new Set<Quest["status"]>(["done", "partial"]);
const CLOSED_UNDONE = new Set<Quest["status"]>(["skipped", "forgotten", "abandoned"]);

export const STAT_FOR_CATEGORY: Record<Quest["category"], Stat> = {
  general: "discipline",
  ics: "discipline",
  utilities: "discipline",
  government: "discipline",
  subscription: "discipline",
  delivery: "discipline",
  personal: "discipline",
  travel: "discipline",
  health: "health",
  jobs: "career",
  learning: "career",
};

/** Local date a quest was finished on, or null. */
function finishedOn(q: Quest): string | null {
  return FINISHED.has(q.status) && q.completed_at ? isoDate(new Date(q.completed_at)) : null;
}

export function totalXp(quests: Quest[]): number {
  return quests.reduce((sum, q) => sum + (FINISHED.has(q.status) ? (q.xp_awarded ?? 0) : 0), 0);
}

export function stats(quests: Quest[]): Record<Stat, number> {
  const out: Record<Stat, number> = { discipline: 0, health: 0, career: 0 };
  for (const q of quests) {
    if (FINISHED.has(q.status)) out[STAT_FOR_CATEGORY[q.category]] += q.xp_awarded ?? 0;
  }
  return out;
}

/**
 * Consecutive days (ending today or yesterday) with at least one finished quest.
 * Today without a finish yet doesn't break the streak; it is "at risk" instead.
 */
export function streak(quests: Quest[], now: Date): { days: number; atRisk: boolean } {
  const days = new Set(quests.map(finishedOn).filter((d): d is string => d !== null));
  const today = isoDate(now);
  let cursor = days.has(today) ? today : addDays(today, -1);
  let count = 0;
  while (days.has(cursor)) {
    count++;
    cursor = addDays(cursor, -1);
  }
  return { days: count, atRisk: count > 0 && !days.has(today) };
}

/**
 * Completion rate over the last `windowDays` days of scheduled daily quests that are settled
 * (finished, or closed undone). Partial counts half.
 */
export function completionRate(
  quests: Quest[],
  now: Date,
  windowDays = 7,
): { rate: number | null; settled: number } {
  const from = addDays(isoDate(now), -(windowDays - 1));
  let settled = 0;
  let score = 0;
  for (const q of quests) {
    if (q.cadence !== "daily" || !q.scheduled_for || q.scheduled_for < from) continue;
    if (q.status === "done") score += 1;
    else if (q.status === "partial") score += 0.5;
    else if (!CLOSED_UNDONE.has(q.status)) continue;
    settled++;
  }
  return { rate: settled === 0 ? null : score / settled, settled };
}

/** Mood picks the dialogue variant bucket. Too little data reads as neutral. */
export function mood(rate: number | null, sample = Infinity): Mood {
  if (rate === null || sample < 3) return "neutral";
  if (rate >= 0.7) return "pleased";
  if (rate >= 0.4) return "neutral";
  return "concerned";
}

export type Capacity = { availableMin: number; plannedMin: number; over: boolean };

/** Free hours (manual for now) x focus factor vs the planned effort still open today. */
export function capacity(cfg: Config["capacity"], quests: Quest[], now: Date): Capacity {
  const weekend = now.getDay() === 0 || now.getDay() === 6;
  const hours = weekend ? cfg.weekend_hours : cfg.weekday_hours;
  const availableMin = Math.round(hours * 60 * cfg.focus_factor);
  const today = isoDate(now);
  const plannedMin = quests
    .filter((q) => q.cadence === "daily" && q.scheduled_for === today)
    .filter((q) => !FINISHED.has(q.status) && !CLOSED_UNDONE.has(q.status))
    .filter((q) => q.status !== "deferred")
    .reduce((sum, q) => sum + q.estimate_min, 0);
  return { availableMin, plannedMin, over: plannedMin > availableMin };
}

export type BoardTrigger = "all_done" | "half_by_noon" | "nothing_by_15" | "over_capacity";

/** Board-level line for today's daily quests, most notable first. */
export function boardTrigger(todays: Quest[], cap: Capacity, now: Date): BoardTrigger | null {
  const planned = todays.filter((q) => q.status !== "deferred");
  if (planned.length === 0) return null;
  const done = planned.filter((q) => FINISHED.has(q.status)).length;
  const settled = planned.filter((q) => FINISHED.has(q.status) || CLOSED_UNDONE.has(q.status));
  if (settled.length === planned.length && done > 0) return "all_done";
  if (cap.over) return "over_capacity";
  const hour = now.getHours();
  if (hour >= 15 && done === 0) return "nothing_by_15";
  if (hour < 12 && done * 2 >= planned.length) return "half_by_noon";
  return null;
}
