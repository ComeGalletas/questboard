// Browser-local sample data so the board can be tried before Supabase exists.
// Nothing here leaves the browser; clearing site data resets it.

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
import { addDays, isoDate } from "../game/dates.ts";
import { baseXp } from "../game/xp.ts";
import type { NewQuest, Store } from "./store.ts";

const KEY = "questboard.demo.v2";

type DemoState = { quests: Quest[]; proposals: QuestProposal[]; lines: PersonaLine[] };

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

function seed(now: Date): DemoState {
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
  // What a runner's daily_am might have proposed, so the review strip has something to show.
  const created = now.toISOString();
  const review = quests[1];
  const proposals: QuestProposal[] = [
    {
      id: uuid(),
      op: "add",
      status: "pending",
      created_at: created,
      payload: {
        op: "add",
        reason: "No quest moves the 10k goal forward this week.",
        quest: {
          title: "Stride drills",
          persona: "coach",
          cadence: "daily",
          category: "health",
          estimate_min: 10,
          priority: 2,
          scheduled_for: today,
        },
      },
      lines: [
        {
          trigger: "completed_on_time",
          variant: 1,
          condition: "any",
          text: "Quick feet! Drills done.",
        },
        {
          trigger: "assigned",
          variant: 1,
          condition: "any",
          text: "Ten minutes of drills. Short and sharp.",
        },
      ],
    },
    {
      id: uuid(),
      op: "update",
      quest_id: review.id,
      status: "pending",
      created_at: created,
      payload: {
        op: "update",
        quest_id: review.id,
        reason: "Your last reviews took about 45 minutes.",
        changes: { estimate_min: 45 },
      },
    },
  ];
  return { quests, proposals, lines: [] };
}

export class DemoStore implements Store {
  readonly kind = "demo" as const;
  private listeners = new Set<() => void>();

  private load(): DemoState {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) return JSON.parse(raw) as DemoState;
    } catch {
      // storage unavailable: fall through to fresh seed data
    }
    const state = seed(new Date());
    this.save(state);
    return state;
  }

  private save(state: DemoState): void {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      // private mode etc.: demo still works for this page view
    }
    for (const fn of this.listeners) fn();
  }

  async listQuests(): Promise<Quest[]> {
    return this.load().quests;
  }

  async insertQuest(q: NewQuest): Promise<Quest> {
    const state = this.load();
    const quest = make(q);
    state.quests.push(quest);
    this.save(state);
    return quest;
  }

  async updateQuest(id: string, patch: QuestPatch | QuestChangesPatch): Promise<Quest> {
    const state = this.load();
    const i = state.quests.findIndex((q) => q.id === id);
    if (i < 0) throw new Error("quest not found");
    state.quests[i] = { ...state.quests[i], ...patch, updated_at: new Date().toISOString() };
    this.save(state);
    return state.quests[i];
  }

  async listPendingProposals(): Promise<QuestProposal[]> {
    return this.load().proposals.filter((p) => p.status === "pending");
  }

  async decideProposal(id: string, status: "accepted" | "rejected" | "superseded") {
    const state = this.load();
    state.proposals = state.proposals.map((p) =>
      p.id === id ? { ...p, status, decided_at: new Date().toISOString() } : p,
    );
    this.save(state);
  }

  async insertLines(questId: string, persona: string, lines: FallbackLine[]) {
    const state = this.load();
    const created = new Date().toISOString();
    for (const l of lines) {
      state.lines.push({
        ...l,
        id: uuid(),
        quest_id: questId,
        persona,
        used_at: null,
        created_at: created,
      } as PersonaLine);
    }
    this.save(state);
  }

  async createLiveRequest(): Promise<string> {
    throw new Error("The setup assistant needs the PC runner; it isn't available in demo mode.");
  }

  async getLiveRequest(): Promise<null> {
    return null;
  }

  async saveConfig(): Promise<void> {
    throw new Error("Demo mode uses a fixed config.");
  }

  async savePushSubscription(): Promise<void> {
    // Demo mode never sends pushes.
  }

  async recordFeedback(): Promise<void> {
    // Demo mode keeps no feedback log.
  }

  async getConfig(): Promise<Config> {
    return DEMO_CONFIG;
  }

  async listLines(): Promise<PersonaLine[]> {
    return this.load().lines;
  }

  async markLineUsed(id: string, at: string): Promise<void> {
    const state = this.load();
    state.lines = state.lines.map((l) => (l.id === id ? { ...l, used_at: at } : l));
    this.save(state);
  }

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
