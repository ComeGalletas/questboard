// The weekly / monthly retro on the Week / Month board. Pure code: which retro to show and
// what to save. The runner writes the questions (model-written, fixed as fallback); answers
// reach later planning prompts as the user's own reflection.

import type { Retro } from "@questboard/schema";

/** A retro stays on the board this long after its period ended; then it quietly lapses. */
export const SHOW_DAYS = 10;
export const MAX_ANSWER = 500;

/** The newest open retro that's still recent enough to ask, or null. */
export function retroToShow(retros: Retro[], today: string): Retro | null {
  const open = retros.filter(
    (r) => r.status === "open" && daysBetween(r.period_end, today) <= SHOW_DAYS,
  );
  return open.sort((a, b) => b.period_start.localeCompare(a.period_start))[0] ?? null;
}

function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000);
}

/** What to save from the form: trimmed answers; all blank counts as a skip. */
export function retroPatch(
  retro: Retro,
  form: Record<string, string>,
  at: Date,
): Pick<Retro, "status" | "answers" | "answered_at"> {
  const answers = retro.questions
    .map((q) => ({ id: q.id, answer: (form[q.id] ?? "").trim().slice(0, MAX_ANSWER) }))
    .filter((a) => a.answer);
  return answers.length
    ? { status: "answered", answers, answered_at: at.toISOString() }
    : { status: "skipped", answers: null, answered_at: at.toISOString() };
}

export function periodLabel(retro: Pick<Retro, "cadence" | "period_start" | "period_end">): string {
  const fmt = (d: string, opts: Intl.DateTimeFormatOptions) =>
    new Date(`${d}T12:00:00`).toLocaleDateString(undefined, opts);
  return retro.cadence === "weekly"
    ? `Week of ${fmt(retro.period_start, { month: "short", day: "numeric" })}`
    : fmt(retro.period_start, { month: "long", year: "numeric" });
}
