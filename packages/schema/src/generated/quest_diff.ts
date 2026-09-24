/* Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`. */

export type QuestOp = AddOp | UpdateOp | DropOp;

/**
 * What a model proposes against the current quest log. The user accepts or rejects each op; the model never writes quests directly.
 */
export interface QuestDiff {
  /**
   * @maxItems 50
   */
  ops: QuestOp[];
  summary?: string | null;
}
export interface AddOp {
  op: "add";
  quest: QuestDraft;
  reason: string;
}
export interface QuestDraft {
  title: string;
  notes?: string | null;
  /**
   * Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
   */
  persona: string;
  cadence: "daily" | "weekly" | "monthly";
  /**
   * Quest / record category. Non-general values match the email extractors.
   */
  category:
    | "general"
    | "ics"
    | "utilities"
    | "government"
    | "health"
    | "delivery"
    | "subscription"
    | "jobs"
    | "learning"
    | "personal"
    | "travel";
  estimate_min: number;
  scheduled_for?: string | null;
  deadline?: string | null;
  priority: number;
  parent_id?: string | null;
}
export interface UpdateOp {
  op: "update";
  quest_id: string;
  changes: QuestChanges;
  reason: string;
}
export interface QuestChanges {
  title?: string;
  notes?: string | null;
  /**
   * Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
   */
  persona?: string;
  estimate_min?: number;
  scheduled_for?: string | null;
  deadline?: string | null;
  priority?: number;
}
export interface DropOp {
  op: "drop";
  quest_id: string;
  reason: string;
}
