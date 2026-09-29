// What the last planning run said about a board when it proposed nothing. Pure code (P2).

import type { LLMRun } from "@questboard/schema";
import { addDays } from "../game/dates.ts";
import { boardRange, type Board } from "./board.ts";

/** The llm_runs columns the app reads (succeeded planning runs only). */
export type PlanRun = Pick<LLMRun, "job" | "date" | "ops_count" | "summary" | "finished_at">;

export const PLANNING_JOBS = ["daily_am", "weekly", "monthly"] as const;

const BOARD_JOB = { today: "daily_am", week: "weekly", month: "monthly" } as const;
const PERIOD_WORD: Record<Board, string> = {
  today: "for today",
  week: "this week",
  month: "this month",
};

/** First day a run plans: today (daily_am), the next Monday (weekly), the month (monthly). */
function periodStart(run: PlanRun): string {
  if (run.job === "weekly") {
    const [y, m, d] = run.date.split("-").map(Number);
    const weekday = (new Date(y, m - 1, d).getDay() + 6) % 7; // Monday = 0
    return addDays(run.date, 7 - weekday);
  }
  return run.date;
}

/**
 * The notice for a board whose latest planning run for the current period proposed zero ops,
 * or null. Forced re-runs finish later, so the most recent success decides.
 */
export function emptyPlanNotice(
  board: Board,
  runs: PlanRun[],
  now: Date,
): { text: string; summary: string | null } | null {
  const { from } = boardRange(board, now);
  const latest = runs
    .filter((r) => r.job === BOARD_JOB[board] && periodStart(r) === from)
    .sort((a, b) => (b.finished_at ?? "").localeCompare(a.finished_at ?? ""))[0];
  if (!latest || latest.ops_count !== 0) return null;
  return {
    text: `The planner proposed nothing ${PERIOD_WORD[board]}.`,
    summary: latest.summary?.trim() || null,
  };
}
