import type { SupabaseClient } from "@supabase/supabase-js";
import type {
  Config,
  FallbackLine,
  MilestoneReached,
  Notification,
  PersonaLine,
  Quest,
  QuestProposal,
  RunnerState,
} from "@questboard/schema";
import type { LiveKind, LiveKinds, LiveRequest } from "./store.ts";
import type { QuestPatch } from "../game/actions.ts";
import type { EditPatch } from "../game/edit.ts";
import type { QuestChangesPatch } from "../game/proposals.ts";
import { NOTIFICATION_COLUMNS } from "../lib/pc-notifications.ts";
import { PLANNING_JOBS, type PlanRun } from "../lib/planner.ts";
import type { NewQuest, Store } from "./store.ts";

/** How far back the log is loaded; enough for streaks, mood and XP totals for now. */
const HISTORY_DAYS = 400;

export class SupabaseStore implements Store {
  readonly kind = "supabase" as const;
  constructor(private readonly db: SupabaseClient) {}

  async listQuests(): Promise<Quest[]> {
    const since = new Date(Date.now() - HISTORY_DAYS * 86_400_000).toISOString();
    const { data, error } = await this.db
      .from("quests")
      .select("*")
      .gte("created_at", since)
      .order("priority")
      .order("created_at");
    if (error) throw new Error(error.message);
    return data as Quest[];
  }

  async insertQuest(q: NewQuest): Promise<Quest> {
    const { data, error } = await this.db.from("quests").insert(q).select().single();
    if (error) throw new Error(error.message);
    return data as Quest;
  }

  async updateQuest(id: string, patch: QuestPatch | QuestChangesPatch | EditPatch): Promise<Quest> {
    const { data, error } = await this.db
      .from("quests")
      .update(patch)
      .eq("id", id)
      .select()
      .single();
    if (error) throw new Error(error.message);
    return data as Quest;
  }

  async deleteQuests(ids: string[]): Promise<void> {
    // One at a time, in order: steps before their parent.
    for (const id of ids) {
      const { error } = await this.db.from("quests").delete().eq("id", id);
      if (error) throw new Error(error.message);
    }
  }

  async getConfig(): Promise<Config | null> {
    const { data } = await this.db.from("config").select("data").maybeSingle();
    return (data?.data as Config | undefined) ?? null;
  }

  async listLines(): Promise<PersonaLine[]> {
    const since = new Date(Date.now() - 8 * 86_400_000).toISOString();
    const { data } = await this.db.from("persona_lines").select("*").gte("created_at", since);
    return (data as PersonaLine[] | null) ?? [];
  }

  async markLineUsed(id: string, at: string): Promise<void> {
    await this.db.from("persona_lines").update({ used_at: at }).eq("id", id);
  }

  async getRunnerState(): Promise<RunnerState | null> {
    const { data } = await this.db.from("runner_state").select("*").maybeSingle();
    return (data as RunnerState | null) ?? null;
  }

  async listPendingProposals(): Promise<QuestProposal[]> {
    const { data, error } = await this.db
      .from("quest_proposals")
      .select("id,run_id,op,quest_id,payload,lines,status,decided_at,created_at")
      .eq("status", "pending")
      .order("created_at");
    if (error) throw new Error(error.message);
    return data as QuestProposal[];
  }

  async decideProposal(id: string, status: "accepted" | "rejected" | "superseded") {
    const { error } = await this.db
      .from("quest_proposals")
      .update({ status, decided_at: new Date().toISOString() })
      .eq("id", id);
    if (error) throw new Error(error.message);
  }

  async listPlanRuns(): Promise<PlanRun[]> {
    const since = new Date(Date.now() - 40 * 86_400_000).toISOString().slice(0, 10);
    const { data, error } = await this.db
      .from("llm_runs")
      .select("job,date,ops_count,summary,finished_at")
      .in("job", [...PLANNING_JOBS])
      .eq("status", "succeeded")
      .gte("date", since)
      .order("finished_at", { ascending: false });
    if (error) throw new Error(error.message);
    return data as PlanRun[];
  }

  async insertLines(questId: string, persona: string, lines: FallbackLine[]) {
    if (lines.length === 0) return;
    const rows = lines.map((l) => ({ ...l, quest_id: questId, persona }));
    const { error } = await this.db.from("persona_lines").insert(rows);
    if (error) throw new Error(error.message);
  }

  async createLiveRequest<K extends LiveKind>(
    kind: K,
    payload: LiveKinds[K]["payload"],
  ): Promise<string> {
    const { data, error } = await this.db
      .from("pending_live_requests")
      .insert({ kind, payload, origin: "mobile" })
      .select("id")
      .single();
    if (error) throw new Error(error.message);
    return (data as { id: string }).id;
  }

  async getLiveRequest<K extends LiveKind = "setup_assistant">(
    id: string,
  ): Promise<LiveRequest<LiveKinds[K]["result"]> | null> {
    const { data, error } = await this.db
      .from("pending_live_requests")
      .select("status,result,error")
      .eq("id", id)
      .maybeSingle();
    if (error) throw new Error(error.message);
    return (data as LiveRequest<LiveKinds[K]["result"]> | null) ?? null;
  }

  async deleteLiveRequest(id: string): Promise<void> {
    const { error } = await this.db.from("pending_live_requests").delete().eq("id", id);
    if (error) throw new Error(error.message);
  }

  async saveConfig(config: Config): Promise<void> {
    const { error } = await this.db
      .from("config")
      .update({ data: config })
      .not("user_id", "is", null);
    if (error) throw new Error(error.message);
  }

  async savePushSubscription(sub: {
    endpoint: string;
    p256dh: string;
    auth: string;
    user_agent: string;
  }) {
    const { error } = await this.db
      .from("push_subscriptions")
      .upsert(sub, { onConflict: "user_id,endpoint" });
    if (error) throw new Error(error.message);
  }

  async recordFeedback(row: {
    quest_id: string | null;
    action: "accepted" | "rejected";
    diff_op: QuestProposal["payload"];
  }) {
    const { error } = await this.db.from("quest_feedback").insert(row);
    if (error) throw new Error(error.message);
  }

  async listReachedMilestones(): Promise<MilestoneReached[]> {
    const { data, error } = await this.db
      .from("milestones_reached")
      .select("key,milestone,label,reached_at");
    if (error) throw new Error(error.message);
    return (data ?? []) as MilestoneReached[];
  }

  async recordMilestones(rows: MilestoneReached[]): Promise<void> {
    if (!rows.length) return;
    const { error } = await this.db
      .from("milestones_reached")
      .upsert(rows, { onConflict: "user_id,key", ignoreDuplicates: true });
    if (error) throw new Error(error.message);
  }

  async listPcNotifications(sinceIso: string): Promise<Notification[]> {
    const { data, error } = await this.db
      .from("notifications")
      .select(NOTIFICATION_COLUMNS)
      .contains("channels", ["pc"])
      .not("sent_at", "is", null)
      .is("pc_shown_at", null)
      .gte("sent_at", sinceIso)
      .order("sent_at", { ascending: false });
    if (error) throw new Error(error.message);
    return (data ?? []) as Notification[];
  }

  async markPcShown(ids: string[], at: string) {
    if (!ids.length) return;
    const { error } = await this.db.from("notifications").update({ pc_shown_at: at }).in("id", ids);
    if (error) throw new Error(error.message);
  }

  subscribeNotifications(onChange: () => void): () => void {
    const channel = this.db
      .channel("questboard-notifications")
      .on("postgres_changes", { event: "*", schema: "public", table: "notifications" }, onChange)
      .subscribe();
    return () => {
      this.db.removeChannel(channel);
    };
  }

  subscribe(onChange: () => void): () => void {
    const channel = this.db.channel("questboard");
    for (const table of [
      "quests",
      "persona_lines",
      "runner_state",
      "quest_proposals",
      "pending_live_requests",
    ]) {
      channel.on("postgres_changes", { event: "*", schema: "public", table }, onChange);
    }
    channel.subscribe();
    return () => {
      this.db.removeChannel(channel);
    };
  }
}
