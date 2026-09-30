// Milestones the personas celebrate. Pure code (P2): detected from the quest log, never by a
// model. The ids are the registry in packages/schema (common MilestoneId). To add a milestone:
// add the id there, then a detector here (DETECTORS is a Record over the ids, so the compiler
// asks for it), and optionally pack lines; packs without one use their generic milestone lines.

import type { MilestoneReached, Quest } from "@questboard/schema";
import { addDays, isoDate } from "./dates.ts";
import type { Placeholders } from "./lines.ts";
import { streak } from "./progress.ts";
import { levelForXp } from "./xp.ts";

export type MilestoneId = MilestoneReached["milestone"];

export type Reached = {
  milestone: MilestoneId;
  /** Unique per occurrence; celebrated once (milestones_reached). */
  key: string;
  /** Fills {milestone}. */
  label: string;
  /** When it was reached: only fresh milestones are celebrated, older ones are just recorded. */
  at: Date;
  /** Other placeholders the line may use. */
  values?: Placeholders;
  /** Who should cheer (default: the lead persona). */
  persona?: string;
};

type Detector = (quests: Quest[], now: Date) => Reached[];

export const STREAK_STEPS = [3, 7, 14, 30] as const;
/** Celebrate only milestones reached this recently; first launch and long absences stay quiet. */
export const FRESH_MS = 36 * 60 * 60 * 1000;
const FINISHED = new Set<Quest["status"]>(["done", "partial"]);
const PERFECT_MIN = 3; // a week needs at least this many daily quests to count

function localNoon(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d, 12);
}

/** Monday of the week that holds `day` (local). */
function mondayOf(day: string): string {
  const dow = localNoon(day).getDay(); // 0 = Sunday
  return addDays(day, -((dow + 6) % 7));
}

export const DETECTORS: Record<MilestoneId, Detector> = {
  // The highest step of the current run of days; a new run can earn the steps again.
  streak(quests, now) {
    const s = streak(quests, now);
    const step = [...STREAK_STEPS].reverse().find((t) => s.days >= t);
    if (!step) return [];
    const end = s.atRisk ? addDays(isoDate(now), -1) : isoDate(now);
    const start = addDays(end, -(s.days - 1));
    return [
      {
        milestone: "streak",
        key: `streak:${step}:${start}`,
        label: `${step}-day streak`,
        at: localNoon(addDays(start, step - 1)),
        values: { streak: String(s.days) },
      },
    ];
  },

  // Each level reached, dated by the finish that crossed it.
  level_up(quests) {
    const finished = quests
      .filter((q) => FINISHED.has(q.status) && q.completed_at && (q.xp_awarded ?? 0) > 0)
      .sort((a, b) => a.completed_at!.localeCompare(b.completed_at!));
    const out: Reached[] = [];
    let xp = 0;
    let level = 1;
    for (const q of finished) {
      xp += q.xp_awarded ?? 0;
      const now = levelForXp(xp);
      if (now > level) {
        level = now;
        out.push({
          milestone: "level_up",
          key: `level:${level}`,
          label: `Level ${level}`,
          at: new Date(q.completed_at!),
        });
      }
    }
    return out;
  },

  // A weekly or monthly quest finished (all its steps or on its own).
  period_done(quests) {
    return quests
      .filter((q) => q.cadence !== "daily" && q.status === "done" && q.completed_at)
      .map((q) => ({
        milestone: "period_done" as const,
        key: `period_done:${q.id}`,
        label: `${q.title} done`.slice(0, 80),
        at: new Date(q.completed_at!),
        persona: q.persona,
      }));
  },

  // Last complete week (Mon–Sun): every daily quest on it done, none forgotten.
  perfect_week(quests, now) {
    const monday = addDays(mondayOf(isoDate(now)), -7);
    const sunday = addDays(monday, 6);
    const inWeek = (d: string | null | undefined) => !!d && d >= monday && d <= sunday;
    const dailies = quests.filter((q) => q.cadence === "daily" && inWeek(q.scheduled_for));
    const forgotten = quests.some((q) => (q.forgotten_on ?? []).some(inWeek));
    if (dailies.length < PERFECT_MIN || forgotten || dailies.some((q) => q.status !== "done"))
      return [];
    return [
      {
        milestone: "perfect_week",
        key: `perfect_week:${monday}`,
        label: "a perfect week",
        at: localNoon(addDays(sunday, 1)),
      },
    ];
  },
};

/** Everything reached so far, from every registered detector. */
export function detectMilestones(quests: Quest[], now: Date): Reached[] {
  return (Object.keys(DETECTORS) as MilestoneId[]).flatMap((id) => DETECTORS[id](quests, now));
}

/**
 * Milestones not recorded yet, split into the ones to celebrate (fresh, most recent first) and
 * the ones to record quietly (reached too long ago, e.g. before the app first saw them).
 */
export function newMilestones(
  reached: Reached[],
  known: ReadonlySet<string>,
  now: Date,
): { celebrate: Reached[]; quiet: Reached[] } {
  const unseen = reached.filter((r) => !known.has(r.key));
  const fresh = (r: Reached) => now.getTime() - r.at.getTime() <= FRESH_MS;
  return {
    celebrate: unseen.filter(fresh).sort((a, b) => b.at.getTime() - a.at.getTime()),
    quiet: unseen.filter((r) => !fresh(r)),
  };
}
