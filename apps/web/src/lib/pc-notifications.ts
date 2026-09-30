// PC delivery of notifications in the desktop shell (pure; P2). The runner decides when a
// notification is released (sent_at, after quiet hours) and dedups it; the shell shows released
// rows with the "pc" channel once each, as a Windows toast plus a persona reaction.

import type { Notification } from "@questboard/schema";
import type { SpriteState } from "../data/reaction.tsx";

/** Older released rows are skipped: don't replay yesterday's news after the PC was off. */
export const MAX_AGE_MS = 12 * 60 * 60 * 1000;
/** At most this many toasts at once (the newest); the rest are marked shown silently. */
export const MAX_TOASTS = 3;

export type Due = { show: Notification[]; skip: Notification[] };

/**
 * Splits notifications the PC hasn't handled into the ones to show (newest first, capped)
 * and the ones to mark shown without a toast (too old, or over the cap).
 */
export function pcDue(rows: Notification[], now: Date, handled: ReadonlySet<string>): Due {
  const waiting = rows
    .filter((n) => n.channels.includes("pc") && n.sent_at && !n.pc_shown_at && !handled.has(n.id))
    .sort((a, b) => Date.parse(b.sent_at!) - Date.parse(a.sent_at!));
  const fresh = waiting.filter((n) => now.getTime() - Date.parse(n.sent_at!) <= MAX_AGE_MS);
  const show = fresh.slice(0, MAX_TOASTS);
  const skip = waiting.filter((n) => !show.includes(n));
  return { show, skip };
}

const DEFAULT_TITLES: Record<Notification["kind"], string> = {
  day_ready: "Today's quests are ready",
  day_recap: "Day recap",
  week_ready: "This week's plan is ready",
  month_ready: "This month's plan is ready",
  quest_due: "Due soon",
  quest_overdue: "Overdue",
  capacity_alert: "Over capacity",
  streak_risk: "Streak at risk",
  persona_speech: "Questboard",
  runner_stale: "Runner offline",
  live_pending: "Waiting for your PC",
};

/** What the toast says; falls back to a title per kind when the row has none. */
export function toastFor(n: Notification): { title: string; body: string; target: string } {
  return {
    title: (n.title || DEFAULT_TITLES[n.kind]).slice(0, 80),
    body: (n.body ?? "").slice(0, 280),
    target: n.target,
  };
}

/** Sprite state the persona plays for a notification (CLAUDE.md: PC plays the sprite state). */
export function spriteForKind(kind: Notification["kind"]): SpriteState {
  switch (kind) {
    case "day_recap":
      return "happy";
    case "quest_overdue":
    case "capacity_alert":
    case "streak_risk":
    case "runner_stale":
      return "concerned";
    default:
      return "talk";
  }
}
