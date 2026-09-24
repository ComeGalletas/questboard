import type { SupabaseClient } from "@supabase/supabase-js";
import type { Config, PersonaLine, Quest, RunnerState } from "@questboard/schema";
import type { QuestPatch } from "../game/actions.ts";
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

  async updateQuest(id: string, patch: QuestPatch): Promise<Quest> {
    const { data, error } = await this.db
      .from("quests")
      .update(patch)
      .eq("id", id)
      .select()
      .single();
    if (error) throw new Error(error.message);
    return data as Quest;
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

  subscribe(onChange: () => void): () => void {
    const channel = this.db.channel("questboard");
    for (const table of ["quests", "persona_lines", "runner_state"]) {
      channel.on("postgres_changes", { event: "*", schema: "public", table }, onChange);
    }
    channel.subscribe();
    return () => {
      this.db.removeChannel(channel);
    };
  }
}
