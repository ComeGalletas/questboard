// Editing and deleting a quest by hand. Pure code (P2): builds the patch the store applies and
// says what a delete takes with it. The user's own edit, so no proposal round-trip.

import type { Quest } from "@questboard/schema";
import { ACTIVE } from "./actions.ts";
import { endOfLocalDay, isoDate } from "./dates.ts";
import { baseXp, type XpWeights } from "./xp.ts";

export const CATEGORIES: Quest["category"][] = [
  "general",
  "health",
  "learning",
  "jobs",
  "personal",
  "utilities",
  "government",
  "subscription",
  "delivery",
  "travel",
];

export type EditForm = {
  title: string;
  category: Quest["category"];
  persona: string;
  estimate: string;
  priority: number;
  /** scheduled_for, "" = none */
  day: string;
  /** local date of the deadline, "" = none */
  deadline: string;
};

export type EditPatch = Partial<
  Pick<
    Quest,
    | "title"
    | "category"
    | "persona"
    | "estimate_min"
    | "priority"
    | "xp"
    | "scheduled_for"
    | "deadline"
  >
>;

export function editFormFor(q: Quest): EditForm {
  return {
    title: q.title,
    category: q.category,
    persona: q.persona,
    estimate: String(q.estimate_min),
    priority: q.priority,
    day: q.scheduled_for ?? "",
    deadline: q.deadline ? isoDate(new Date(q.deadline)) : "",
  };
}

/**
 * The fields that changed, validated. XP follows estimate / priority / category while the quest
 * is open; a finished quest keeps the XP it was worth (and earned).
 */
export function editPatch(
  q: Quest,
  f: EditForm,
  weights: XpWeights = {},
): { ok: true; patch: EditPatch } | { ok: false; reason: string } {
  const title = f.title.trim();
  if (!title || title.length > 120) return { ok: false, reason: "Title must be 1–120 characters" };
  const estimate = Number(f.estimate);
  if (!Number.isInteger(estimate) || estimate < 1 || estimate > 1440)
    return { ok: false, reason: "Estimate must be 1–1440 whole minutes" };
  if (![1, 2, 3].includes(f.priority)) return { ok: false, reason: "Priority must be 1–3" };
  if (q.scheduled_for && !f.day) return { ok: false, reason: "Pick a day for this quest" };

  const patch: EditPatch = {};
  if (title !== q.title) patch.title = title;
  if (f.category !== q.category) patch.category = f.category;
  if (f.persona !== q.persona) patch.persona = f.persona;
  if (estimate !== q.estimate_min) patch.estimate_min = estimate;
  if (f.priority !== q.priority) patch.priority = f.priority;
  if ((f.day || null) !== (q.scheduled_for ?? null)) patch.scheduled_for = f.day || null;
  const oldDeadline = q.deadline ? isoDate(new Date(q.deadline)) : "";
  if (f.deadline !== oldDeadline)
    patch.deadline = f.deadline ? endOfLocalDay(f.deadline).toISOString() : null;

  const scoring = "estimate_min" in patch || "priority" in patch || "category" in patch;
  if (scoring && ACTIVE.has(q.status)) {
    const xp = baseXp(
      { estimate_min: estimate, priority: f.priority, category: f.category },
      weights,
    );
    if (xp !== q.xp) patch.xp = xp;
  }
  return { ok: true, patch };
}

export type Deletion = { ids: string[]; steps: Quest[]; earnedXp: number };

/** A quest goes with its steps (sub-quests): steps first, then the quest itself. */
export function deletionFor(q: Quest, quests: Quest[]): Deletion {
  const steps = quests.filter((s) => s.parent_id === q.id);
  const earnedXp = [q, ...steps].reduce((sum, s) => sum + (s.xp_awarded ?? 0), 0);
  return { ids: [...steps.map((s) => s.id), q.id], steps, earnedXp };
}

export function deletionMessage(q: Quest, d: Deletion): string {
  const parts = [`Delete “${q.title}”?`];
  if (d.steps.length)
    parts.push(`Its ${d.steps.length} step${d.steps.length > 1 ? "s" : ""} go too.`);
  if (d.earnedXp > 0) parts.push(`The ${d.earnedXp} XP earned is removed.`);
  parts.push("This can't be undone.");
  return parts.join(" ");
}
