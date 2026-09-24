// From a parsed voice command to what the confirmation card shows and, once confirmed, writes.
// Pure code (P2). Nothing here writes: the card calls the store only after a tap or a spoken
// "confirm" (invariant 8).

import type { Config, Quest, VoiceCommand } from "@questboard/schema";
import { ACTIVE, type QuestAction } from "../game/actions.ts";
import { addDays } from "../game/dates.ts";
import { personaForCategory } from "../game/personas.ts";
import { baseXp } from "../game/xp.ts";
import type { NewQuest } from "../data/store.ts";
import { matchQuest } from "./match.ts";

export const DEFAULT_ESTIMATE = 30;
export const DEFAULT_SNOOZE = 30;

export type CreateDraft = {
  kind: "create";
  title: string;
  date: string;
  time: string; // "" = no time
  persona: string;
  estimate: number;
};

export type QuestDraft = {
  kind: "complete" | "snooze" | "defer";
  said: string;
  /** Quests to choose from: the matches first, then every other open quest. */
  candidates: Quest[];
  questId: string | null; // preselected only on a unique match
  minutes: number; // complete: actual time; snooze: duration
  date: string; // defer
};

export type Draft = CreateDraft | QuestDraft | { kind: "whats_next" } | { kind: "unknown" };

export function draftFor(
  cmd: VoiceCommand,
  quests: Quest[],
  config: Pick<Config, "persona_order">,
  today: string,
): Draft {
  switch (cmd.intent) {
    case "create":
      return {
        kind: "create",
        title: cmd.title ?? "",
        date: cmd.date ?? today,
        time: cmd.time ?? "",
        persona: personaForCategory("general", config.persona_order),
        estimate: DEFAULT_ESTIMATE,
      };
    case "complete":
    case "snooze":
    case "defer": {
      const open = quests.filter((q) => ACTIVE.has(q.status));
      const m = matchQuest(cmd.quest ?? "", open);
      const first = m.kind === "match" ? [m.id] : m.kind === "ambiguous" ? m.ids : [];
      const byId = new Map(open.map((q) => [q.id, q]));
      const candidates = [
        ...first.map((id) => byId.get(id)!),
        ...open.filter((q) => !first.includes(q.id)),
      ];
      const questId = m.kind === "match" ? m.id : null;
      const picked = questId ? byId.get(questId) : undefined;
      return {
        kind: cmd.intent,
        said: cmd.quest ?? "",
        candidates,
        questId,
        minutes:
          cmd.intent === "snooze"
            ? (cmd.minutes ?? DEFAULT_SNOOZE)
            : (picked?.estimate_min ?? DEFAULT_ESTIMATE),
        date: cmd.date ?? addDays(today, 1),
      };
    }
    case "whats_next":
      return { kind: "whats_next" };
    default: // unknown; confirm / cancel only mean something while a card is open
      return { kind: "unknown" };
  }
}

/** The quest a confirmed create writes. The time, when said, becomes the deadline that day. */
export function newQuestFrom(d: CreateDraft, config: Pick<Config, "xp_weights">): NewQuest {
  const estimate_min = Math.round(d.estimate);
  const [y, m, day] = d.date.split("-").map(Number);
  const [hh, mm] = d.time ? d.time.split(":").map(Number) : [0, 0];
  return {
    title: d.title.trim().slice(0, 120),
    persona: d.persona,
    cadence: "daily",
    category: "general",
    estimate_min,
    priority: 2,
    xp: baseXp({ estimate_min, priority: 2, category: "general" }, config.xp_weights),
    scheduled_for: d.date,
    deadline: d.time ? new Date(y, m - 1, day, hh, mm).toISOString() : null,
    source: "voice",
  };
}

/** The action a confirmed complete / snooze / defer applies (through applyAction). */
export function actionFrom(d: QuestDraft): QuestAction {
  if (d.kind === "complete") return { kind: "complete", actualMin: d.minutes };
  if (d.kind === "snooze") return { kind: "snooze", minutes: d.minutes };
  return { kind: "defer", to: d.date };
}

/** Problems that keep the Confirm button disabled. */
export function draftProblem(d: CreateDraft | QuestDraft, today: string): string | null {
  if (d.kind === "create") {
    if (!d.title.trim()) return "Say or type a title";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d.date) || d.date < today) return "Pick today or a later day";
    if (!(d.estimate >= 1 && d.estimate <= 1440)) return "Estimate must be 1–1440 minutes";
    return null;
  }
  if (!d.questId) return d.candidates.length ? "Pick the quest" : "No open quest to pick";
  if (d.kind === "defer" && !(d.date > today)) return "Defer needs a later day";
  const min = d.kind === "complete" ? 0 : 1;
  if (!(d.minutes >= min && d.minutes <= 1440)) return `Minutes must be ${min}–1440`;
  return null;
}
