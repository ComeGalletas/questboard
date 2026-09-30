// The app's data access. Two implementations share this interface:
//  - SupabaseStore: the real single-user DB (RLS-protected).
//  - DemoStore: browser-local sample data, for trying the board before Supabase is set up.

import type {
  Config,
  FallbackLine,
  MilestoneReached,
  Notification,
  NotifyTestRequest,
  NotifyTestResult,
  PersonaLine,
  Quest,
  QuestProposal,
  ReplanRequest,
  ReplanResult,
  Retro,
  RunnerState,
  SetupRequest,
  SetupTurn,
  VoiceCommand,
  VoiceFallbackRequest,
} from "@questboard/schema";
import type { QuestPatch } from "../game/actions.ts";
import type { EditPatch } from "../game/edit.ts";
import type { QuestChangesPatch } from "../game/proposals.ts";
import type { PlanRun } from "../lib/planner.ts";

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
  Partial<Pick<Quest, "notes" | "hard_deadline" | "parent_id">>;

export interface Store {
  readonly kind: "supabase" | "demo";
  listQuests(): Promise<Quest[]>;
  insertQuest(q: NewQuest): Promise<Quest>;
  updateQuest(id: string, patch: QuestPatch | QuestChangesPatch | EditPatch): Promise<Quest>;
  /** Hard delete (the user's own correction); dialogue, feedback and proposals cascade. */
  deleteQuests(ids: string[]): Promise<void>;
  getConfig(): Promise<Config | null>;
  listLines(): Promise<PersonaLine[]>;
  markLineUsed(id: string, at: string): Promise<void>;
  getRunnerState(): Promise<RunnerState | null>;
  listPendingProposals(): Promise<QuestProposal[]>;
  decideProposal(id: string, status: "accepted" | "rejected" | "superseded"): Promise<void>;
  /** Recent successful planning runs (daily_am, weekly, monthly), for "proposed nothing". */
  listPlanRuns(): Promise<PlanRun[]>;
  /** Cache dialogue that came with an accepted add, now that the quest has an id. */
  insertLines(questId: string, persona: string, lines: FallbackLine[]): Promise<void>;
  /** P1 request for the runner; resolves with its id. */
  createLiveRequest<K extends LiveKind>(kind: K, payload: LiveKinds[K]["payload"]): Promise<string>;
  getLiveRequest<K extends LiveKind = "setup_assistant">(
    id: string,
  ): Promise<LiveRequest<LiveKinds[K]["result"]> | null>;
  /** Removes a request row (voice transcripts are deleted as soon as they're answered). */
  deleteLiveRequest(id: string): Promise<void>;
  saveConfig(config: Config): Promise<void>;
  savePushSubscription(sub: {
    endpoint: string;
    p256dh: string;
    auth: string;
    user_agent: string;
  }): Promise<void>;
  recordFeedback(row: {
    quest_id: string | null;
    action: "accepted" | "rejected";
    diff_op: QuestProposal["payload"];
  }): Promise<void>;
  /** Recent retros of one cadence, newest first. */
  listRetros(cadence: Retro["cadence"]): Promise<Retro[]>;
  /** The user's answers (or a skip). */
  saveRetro(id: string, patch: Pick<Retro, "status" | "answers" | "answered_at">): Promise<void>;
  /** Milestones already celebrated (or recorded quietly). */
  listReachedMilestones(): Promise<MilestoneReached[]>;
  /** Record milestones; ones already recorded (same key) are left as they are. */
  recordMilestones(rows: MilestoneReached[]): Promise<void>;
  /** Calls back on any change to quests / persona_lines / runner_state / quest_proposals. */
  subscribe(onChange: () => void): () => void;
  /** Released notifications for the PC channel not shown on the PC yet (desktop shell). */
  listPcNotifications(sinceIso: string): Promise<Notification[]>;
  markPcShown(ids: string[], at: string): Promise<void>;
  /** Calls back when notifications change (the runner inserts or releases one). */
  subscribeNotifications(onChange: () => void): () => void;
}

/** Live request kinds the app sends, with their payload and result shapes. */
export type LiveKinds = {
  setup_assistant: { payload: SetupRequest; result: SetupTurn };
  replan: { payload: ReplanRequest; result: ReplanResult };
  notify_test: { payload: NotifyTestRequest; result: NotifyTestResult };
  voice_fallback: { payload: VoiceFallbackRequest; result: VoiceCommand };
};
export type LiveKind = keyof LiveKinds;

export type LiveRequest<R = SetupTurn> = {
  status: "pending" | "running" | "done" | "failed" | "cancelled";
  result: R | null;
  error: string | null;
};
