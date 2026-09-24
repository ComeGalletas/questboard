// The app's data access. Two implementations share this interface:
//  - SupabaseStore: the real single-user DB (RLS-protected).
//  - DemoStore: browser-local sample data, for trying the board before Supabase is set up.

import type {
  Config,
  FallbackLine,
  PersonaLine,
  Quest,
  QuestProposal,
  RunnerState,
} from "@questboard/schema";
import type { QuestPatch } from "../game/actions.ts";
import type { QuestChangesPatch } from "../game/proposals.ts";

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
  updateQuest(id: string, patch: QuestPatch | QuestChangesPatch): Promise<Quest>;
  getConfig(): Promise<Config | null>;
  listLines(): Promise<PersonaLine[]>;
  markLineUsed(id: string, at: string): Promise<void>;
  getRunnerState(): Promise<RunnerState | null>;
  listPendingProposals(): Promise<QuestProposal[]>;
  decideProposal(id: string, status: "accepted" | "rejected" | "superseded"): Promise<void>;
  /** Cache dialogue that came with an accepted add, now that the quest has an id. */
  insertLines(questId: string, persona: string, lines: FallbackLine[]): Promise<void>;
  recordFeedback(row: {
    quest_id: string | null;
    action: "accepted" | "rejected";
    diff_op: QuestProposal["payload"];
  }): Promise<void>;
  /** Calls back on any change to quests / persona_lines / runner_state / quest_proposals. */
  subscribe(onChange: () => void): () => void;
}
