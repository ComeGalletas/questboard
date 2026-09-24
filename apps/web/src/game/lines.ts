// Persona line selection: trigger + mood condition + no-repeat + placeholder fill. Pure (P2).
// Cached lines (authored by the runner) win; pack fallback lines cover gaps and offline.

import type { FallbackLine, PersonaLine } from "@questboard/schema";
import type { Mood } from "./progress.ts";

export type Placeholders = Partial<
  Record<"time_left" | "streak" | "days_carried" | "actual_vs_estimate" | "next_quest", string>
>;

export type Candidate = Pick<PersonaLine, "trigger" | "condition" | "text" | "variant"> & {
  id?: string;
  used_at?: string | null;
};

export type Picked = { text: string; id?: string; source: "cache" | "fallback" };

const PLACEHOLDER = /\{(\w+)\}/g;

function fillable(text: string, values: Placeholders): boolean {
  for (const [, key] of text.matchAll(PLACEHOLDER)) {
    if (!values[key as keyof Placeholders]) return false;
  }
  return true;
}

export function fill(text: string, values: Placeholders): string {
  return text.replace(PLACEHOLDER, (m, key: string) => values[key as keyof Placeholders] ?? m);
}

/** Mood-specific lines first, then "any"; unused before used; oldest use first. */
function pickFrom(
  lines: Candidate[],
  trigger: Candidate["trigger"],
  mood: Mood,
  values: Placeholders,
  random: () => number,
): Candidate | null {
  const usable = lines.filter((l) => l.trigger === trigger && fillable(l.text, values));
  for (const cond of [mood, "any"] as const) {
    const pool = usable.filter((l) => l.condition === cond);
    if (pool.length === 0) continue;
    const unused = pool.filter((l) => !l.used_at);
    if (unused.length > 0) return unused[Math.floor(random() * unused.length)];
    return [...pool].sort((a, b) => (a.used_at ?? "").localeCompare(b.used_at ?? ""))[0];
  }
  return null;
}

export function selectLine(opts: {
  trigger: Candidate["trigger"];
  mood: Mood;
  cached: Candidate[];
  fallback: FallbackLine[];
  values?: Placeholders;
  random?: () => number;
}): Picked | null {
  const values = opts.values ?? {};
  const random = opts.random ?? Math.random;
  const cached = pickFrom(opts.cached, opts.trigger, opts.mood, values, random);
  if (cached) return { text: fill(cached.text, values), id: cached.id, source: "cache" };
  const fb = pickFrom(opts.fallback, opts.trigger, opts.mood, values, random);
  return fb ? { text: fill(fb.text, values), source: "fallback" } : null;
}

export function formatDuration(min: number): string {
  const m = Math.max(0, Math.round(min));
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return m % 60 === 0 ? `${h} h` : `${h} h ${m % 60} min`;
}

export function actualVsEstimate(actual: number, estimate: number): string {
  const diff = actual - estimate;
  if (Math.abs(diff) <= Math.max(2, estimate * 0.1)) return "right on estimate";
  return diff > 0 ? `${formatDuration(diff)} over` : `${formatDuration(-diff)} under`;
}
