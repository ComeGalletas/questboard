// What accepting a model proposal does, as pure code (P2). The model proposed; the user decides;
// this turns the decision into ordinary quest writes (invariant 3).

import type { Config, Quest, QuestProposal } from "@questboard/schema";
import type { NewQuest } from "../data/store.ts";
import { boardRange, type Board } from "../lib/board.ts";
import { baseXp } from "./xp.ts";

const ACTIVE = new Set<Quest["status"]>(["open", "in_progress", "snoozed", "deferred", "overdue"]);
const BOARD_FOR: Record<Quest["cadence"], Board> = {
  daily: "today",
  weekly: "week",
  monthly: "month",
};

/** Fields a model-proposed update may touch. Deadlines never come from the model. */
export type QuestChangesPatch = Partial<
  Pick<Quest, "title" | "notes" | "persona" | "estimate_min" | "scheduled_for" | "priority" | "xp">
>;

export type Decision =
  | { kind: "insert"; quest: NewQuest }
  | { kind: "update"; questId: string; patch: QuestChangesPatch }
  | { kind: "drop"; questId: string }
  | { kind: "stale"; reason: string };

export function planAcceptance(
  p: QuestProposal,
  quests: Quest[],
  config: Config,
  now: Date,
): Decision {
  const op = p.payload;
  if (op.op === "add") {
    const q = op.quest;
    return {
      kind: "insert",
      quest: {
        title: q.title,
        notes: q.notes ?? null,
        persona: q.persona,
        cadence: q.cadence,
        category: q.category,
        estimate_min: q.estimate_min,
        priority: q.priority,
        xp: baseXp(q, config.xp_weights),
        scheduled_for: q.scheduled_for ?? boardRange(BOARD_FOR[q.cadence], now).from,
        deadline: null,
        parent_id: q.parent_id ?? null,
        source: "llm",
      },
    };
  }
  const target = quests.find((q) => q.id === op.quest_id);
  if (!target || !ACTIVE.has(target.status)) {
    return { kind: "stale", reason: "that quest is already closed" };
  }
  if (op.op === "drop") return { kind: "drop", questId: target.id };

  const c = op.changes;
  const patch: QuestChangesPatch = {};
  if (c.title !== undefined) patch.title = c.title;
  if (c.notes !== undefined) patch.notes = c.notes;
  if (c.persona !== undefined) patch.persona = c.persona;
  if (c.estimate_min !== undefined) patch.estimate_min = c.estimate_min;
  if (c.scheduled_for !== undefined) patch.scheduled_for = c.scheduled_for;
  if (c.priority !== undefined) patch.priority = c.priority;
  if (patch.estimate_min !== undefined || patch.priority !== undefined) {
    patch.xp = baseXp(
      {
        estimate_min: patch.estimate_min ?? target.estimate_min,
        priority: patch.priority ?? target.priority,
        category: target.category,
      },
      config.xp_weights,
    );
  }
  return { kind: "update", questId: target.id, patch };
}

/** One-line summary for the review strip. */
export function describe(p: QuestProposal, quests: Quest[]): string {
  const op = p.payload;
  if (op.op === "add") return `Add “${op.quest.title}” (${op.quest.estimate_min} min)`;
  const title = quests.find((q) => q.id === op.quest_id)?.title ?? "a quest";
  if (op.op === "drop") return `Drop “${title}”`;
  const parts = Object.entries(op.changes)
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => (k === "estimate_min" ? `estimate → ${v} min` : `${k} → ${v}`));
  return `Change “${title}”: ${parts.join(", ")}`;
}

export function proposalPersona(p: QuestProposal, quests: Quest[]): string | null {
  const op = p.payload;
  if (op.op === "add") return op.quest.persona;
  return quests.find((q) => q.id === op.quest_id)?.persona ?? null;
}

export function cadenceOf(p: QuestProposal, quests: Quest[]): Quest["cadence"] | null {
  const op = p.payload;
  if (op.op === "add") return op.quest.cadence;
  return quests.find((q) => q.id === op.quest_id)?.cadence ?? null;
}
