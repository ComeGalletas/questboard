// Browser-local sample data so the board can be tried before Supabase exists.
// Nothing here leaves the browser; clearing site data resets it.

import type { Config, PersonaLine, Quest, RunnerState } from "@questboard/schema";
import type { QuestPatch } from "../game/actions.ts";
import { addDays, isoDate } from "../game/dates.ts";
import { baseXp } from "../game/xp.ts";
import type { NewQuest, Store } from "./store.ts";

const KEY = "questboard.demo.v1";

export const DEMO_CONFIG: Config = {
  timezone: "America/Bogota",
  goals: [],
  capacity: { weekday_hours: 3, weekend_hours: 5, focus_factor: 0.7 },
  quiet_hours: { start: "22:00", end: "07:00" },
  xp_weights: {},
  llm: { providers: ["claude-cli", "ollama", "claude-api"], per_job: {} },
  persona_order: ["coach", "teacher", "mom", "quartermaster"],
  integrations: { gmail: false, gcal: false },
  features: { three_d: false, mobile_rehydration: false },
  notifications: { persona_speech_per_day: 2, persona_speech_on_mobile: false },
};

function uuid(): string {
  return crypto.randomUUID();
}

function make(q: NewQuest, over: Partial<Quest> = {}): Quest {
  const now = new Date().toISOString();
  return {
    id: uuid(),
    status: "open",
    carries: 0,
    hard_deadline: false,
    created_at: now,
    updated_at: now,
    ...q,
    ...over,
  };
}

function seed(now: Date): Quest[] {
  const today = isoDate(now);
  const draft = (
    title: string,
    persona: string,
    category: Quest["category"],
    estimate_min: number,
    priority: number,
    scheduled_for = today,
    cadence: Quest["cadence"] = "daily",
  ): NewQuest => ({
    title,
    persona,
    category,
    cadence,
    estimate_min,
    priority,
    scheduled_for,
    deadline: null,
    source: "manual",
    xp: baseXp({ estimate_min, priority, category }),
  });
  const quests = [
    make(draft("Easy 5 km run", "coach", "health", 40, 2)),
    make(draft("Review chapter 3 notes", "teacher", "learning", 30, 1)),
    make(draft("Call grandma", "mom", "personal", 20, 2)),
    make(draft("Pay the power bill", "quartermaster", "utilities", 10, 1), {
      deadline: new Date(now.getTime() + 2 * 86_400_000).toISOString(),
      hard_deadline: true,
    }),
    make(draft("Plan next week's meals", "mom", "personal", 45, 2, today, "weekly")),
    make(draft("Finish the online course module", "teacher", "learning", 180, 2, today, "monthly")),
  ];
  // A few finished days so streak, XP and mood have something to show.
  for (let back = 1; back <= 3; back++) {
    const day = addDays(today, -back);
    const q = draft("Morning stretch", "coach", "health", 15, 2, day);
    const done = new Date(`${day}T08:00:00`).toISOString();
    quests.push(make(q, { status: "done", completed_at: done, actual_min: 15, xp_awarded: 15 }));
  }
  return quests;
}

export class DemoStore implements Store {
  readonly kind = "demo" as const;
  private listeners = new Set<() => void>();

  private load(): Quest[] {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) return JSON.parse(raw) as Quest[];
    } catch {
      // storage unavailable: fall through to fresh seed data
    }
    const quests = seed(new Date());
    this.save(quests);
    return quests;
  }

  private save(quests: Quest[]): void {
    try {
      localStorage.setItem(KEY, JSON.stringify(quests));
    } catch {
      // private mode etc.: demo still works for this page view
    }
    for (const fn of this.listeners) fn();
  }

  async listQuests(): Promise<Quest[]> {
    return this.load();
  }

  async insertQuest(q: NewQuest): Promise<Quest> {
    const quest = make(q);
    this.save([...this.load(), quest]);
    return quest;
  }

  async updateQuest(id: string, patch: QuestPatch): Promise<Quest> {
    const quests = this.load();
    const i = quests.findIndex((q) => q.id === id);
    if (i < 0) throw new Error("quest not found");
    quests[i] = { ...quests[i], ...patch, updated_at: new Date().toISOString() };
    this.save(quests);
    return quests[i];
  }

  async getConfig(): Promise<Config> {
    return DEMO_CONFIG;
  }

  async listLines(): Promise<PersonaLine[]> {
    return [];
  }

  async markLineUsed(): Promise<void> {}

  async getRunnerState(): Promise<RunnerState | null> {
    return null;
  }

  subscribe(onChange: () => void): () => void {
    this.listeners.add(onChange);
    return () => this.listeners.delete(onChange);
  }

  static reset(): void {
    try {
      localStorage.removeItem(KEY);
    } catch {
      // ignore
    }
  }
}
