// The app's data access. Two implementations share this interface:
//  - SupabaseStore: the real single-user DB (RLS-protected).
//  - DemoStore: browser-local sample data, for trying the board before Supabase is set up.

import type { Config, PersonaLine, Quest, RunnerState } from "@questboard/schema";
import type { QuestPatch } from "../game/actions.ts";

export type NewQuest = Pick<
  Quest,
  | "title"
  | "persona"
  | "cadence"
  | "category"
  | "estimate_min"
  | "priority"
  | "xp"
  | "scheduled_for"
  | "deadline"
  | "source"
> &
  Partial<Pick<Quest, "notes" | "hard_deadline">>;

export interface Store {
  readonly kind: "supabase" | "demo";
  listQuests(): Promise<Quest[]>;
  insertQuest(q: NewQuest): Promise<Quest>;
  updateQuest(id: string, patch: QuestPatch): Promise<Quest>;
  getConfig(): Promise<Config | null>;
  listLines(): Promise<PersonaLine[]>;
  markLineUsed(id: string, at: string): Promise<void>;
  getRunnerState(): Promise<RunnerState | null>;
  /** Calls back on any change to quests / persona_lines / runner_state. */
  subscribe(onChange: () => void): () => void;
}
