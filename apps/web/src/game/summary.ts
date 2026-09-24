// Everything a board screen shows, derived from the quest log in one pure pass (P2).

import type { Config, Quest } from "@questboard/schema";
import type { Board } from "../lib/board.ts";
import { BOARD_CADENCE, boardRange } from "../lib/board.ts";
import { isoDate } from "./dates.ts";
import {
  boardTrigger,
  capacity,
  completionRate,
  mood,
  stats,
  streak,
  totalXp,
  type BoardTrigger,
  type Capacity,
  type Mood,
  type Stat,
} from "./progress.ts";
import { levelProgress } from "./xp.ts";

const FINISHED = new Set<Quest["status"]>(["done", "partial"]);
const CLOSED = new Set<Quest["status"]>(["done", "partial", "skipped", "forgotten", "abandoned"]);

export type Row = { quest: Quest; carriedFrom: string | null; snoozed: boolean; closed: boolean };

export type Summary = {
  rows: Row[];
  capacity: Capacity;
  streak: { days: number; atRisk: boolean };
  level: { level: number; into: number; span: number };
  xp: number;
  stats: Record<Stat, number>;
  mood: Mood;
  trigger: BoardTrigger | null;
  next: Quest | null;
  speaker: string;
};

function rank(r: Row): number {
  if (r.closed) return 3;
  if (r.snoozed) return 2;
  return r.quest.status === "in_progress" ? 0 : 1;
}

/** Quests on a board: this period's, plus unsettled daily quests from earlier days on Today. */
export function boardRows(quests: Quest[], board: Board, now: Date): Row[] {
  const { from, to } = boardRange(board, now);
  const cadence = BOARD_CADENCE[board];
  const rows: Row[] = [];
  for (const q of quests) {
    if (q.cadence !== cadence || !q.scheduled_for || q.scheduled_for > to) continue;
    const closed = CLOSED.has(q.status);
    const carried = q.scheduled_for < from;
    if (carried && (closed || board !== "today")) continue;
    const snoozed = q.status === "snoozed" && !!q.snoozed_until && new Date(q.snoozed_until) > now;
    rows.push({ quest: q, carriedFrom: carried ? q.scheduled_for : null, snoozed, closed });
  }
  return rows.sort(
    (a, b) =>
      rank(a) - rank(b) ||
      a.quest.priority - b.quest.priority ||
      a.quest.created_at.localeCompare(b.quest.created_at),
  );
}

export function isQuietHours(q: Config["quiet_hours"], now: Date): boolean {
  const hm = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  return q.start <= q.end ? hm >= q.start && hm < q.end : hm >= q.start || hm < q.end;
}

export function summarize(quests: Quest[], config: Config, board: Board, now: Date): Summary {
  const rows = boardRows(quests, board, now);
  const today = isoDate(now);
  const todays = quests.filter((q) => q.cadence === "daily" && q.scheduled_for === today);
  const cap = capacity(config.capacity, quests, now);
  const xp = totalXp(quests);
  const rate = completionRate(quests, now);
  const active = rows.filter((r) => !r.closed && !r.snoozed);

  // Whoever hands out most of the visible quests speaks for the board.
  const counts = new Map<string, number>();
  for (const r of rows) counts.set(r.quest.persona, (counts.get(r.quest.persona) ?? 0) + 1);
  const order = config.persona_order;
  const speaker =
    [...counts.entries()].sort(
      (a, b) => b[1] - a[1] || order.indexOf(a[0]) - order.indexOf(b[0]),
    )[0]?.[0] ??
    order[0] ??
    "coach";

  return {
    rows,
    capacity: cap,
    streak: streak(quests, now),
    level: levelProgress(xp),
    xp,
    stats: stats(quests),
    mood: mood(rate.rate, rate.settled),
    trigger: boardTrigger(todays, cap, now),
    next: active.find((r) => r.quest.status !== "in_progress")?.quest ?? active[0]?.quest ?? null,
    speaker,
  };
}

export function finishedCount(rows: Row[]): number {
  return rows.filter((r) => FINISHED.has(r.quest.status)).length;
}
