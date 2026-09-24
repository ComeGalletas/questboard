// Test helpers shared by the game rule tests.
import type { Quest } from "@questboard/schema";

let n = 0;
export function quest(over: Partial<Quest> = {}): Quest {
  n++;
  return {
    id: `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`,
    title: `Quest ${n}`,
    persona: "coach",
    cadence: "daily",
    category: "general",
    status: "open",
    estimate_min: 30,
    priority: 2,
    xp: 30,
    carries: 0,
    hard_deadline: false,
    source: "manual",
    scheduled_for: "2026-09-25",
    created_at: "2026-09-25T06:00:00Z",
    updated_at: "2026-09-25T06:00:00Z",
    ...over,
  };
}

/** Local wall-clock time on a given date (tests run in any TZ). */
export function at(date: string, hh = 12, mm = 0): Date {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(y, m - 1, d, hh, mm);
}
