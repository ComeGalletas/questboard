// Which scheduled_for dates belong on each board. Local calendar dates (YYYY-MM-DD).

import { isoDate } from "../game/dates.ts";

export type Board = "today" | "week" | "month";

export const BOARD_CADENCE = { today: "daily", week: "weekly", month: "monthly" } as const;

/** Inclusive date range for a board; weeks start on Monday. */
export function boardRange(board: Board, now: Date): { from: string; to: string } {
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (board === "today") return { from: isoDate(d), to: isoDate(d) };
  if (board === "week") {
    const monday = new Date(d);
    monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return { from: isoDate(monday), to: isoDate(sunday) };
  }
  const first = new Date(d.getFullYear(), d.getMonth(), 1);
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  return { from: isoDate(first), to: isoDate(last) };
}
