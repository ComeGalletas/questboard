// XP and levels. Pure code (P2).

import type { Quest } from "@questboard/schema";

export type XpWeights = Record<string, number>;
export type Finish = "early" | "on_time" | "late" | "partial";

const PRIORITY_MULT: Record<number, number> = { 1: 1.5, 2: 1, 3: 0.75 };
const FINISH_MULT: Record<Finish, number> = { early: 1.1, on_time: 1, late: 0.75, partial: 0.5 };

/** XP a quest is worth when created: 1 XP per minute of estimate, rounded to 5, min 5. */
export function baseXp(
  q: Pick<Quest, "estimate_min" | "priority" | "category">,
  weights: XpWeights = {},
): number {
  const raw = q.estimate_min * (PRIORITY_MULT[q.priority] ?? 1) * (weights[q.category] ?? 1);
  return Math.max(5, Math.round(raw / 5) * 5);
}

/** XP actually earned for finishing a quest. */
export function awardedXp(xp: number, finish: Finish): number {
  return Math.round(xp * FINISH_MULT[finish]);
}

/** Total XP needed to reach `level` (level 1 = 0, 2 = 100, 3 = 300, 4 = 600, ...). */
export function xpForLevel(level: number): number {
  return (100 * level * (level - 1)) / 2;
}

export function levelForXp(total: number): number {
  let level = 1;
  while (xpForLevel(level + 1) <= total) level++;
  return level;
}

/** Progress inside the current level, for the XP bar. */
export function levelProgress(total: number): { level: number; into: number; span: number } {
  const level = levelForXp(total);
  const floor = xpForLevel(level);
  return { level, into: total - floor, span: xpForLevel(level + 1) - floor };
}
