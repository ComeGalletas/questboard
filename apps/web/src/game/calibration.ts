// Effort calibration (mirror of runner/engine/calibration.py): median actual/estimate per
// category over finished quests in the last 30 days, >= 3 samples, clamped to 0.5x-3x.

import type { Quest } from "@questboard/schema";

const WINDOW_DAYS = 30;
const MIN_SAMPLES = 3;
const CLAMP: [number, number] = [0.5, 3];

function median(values: number[]): number {
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

export type Calibration = Record<string, { ratio: number; samples: number }>;

export function calibration(quests: Quest[], now: Date): Calibration {
  const since = now.getTime() - WINDOW_DAYS * 86_400_000;
  const ratios: Record<string, number[]> = {};
  for (const q of quests) {
    if (
      (q.status === "done" || q.status === "partial") &&
      q.actual_min != null &&
      q.actual_min > 0 &&
      q.completed_at &&
      Date.parse(q.completed_at) >= since
    ) {
      (ratios[q.category] ??= []).push(q.actual_min / q.estimate_min);
    }
  }
  const out: Calibration = {};
  for (const [category, values] of Object.entries(ratios)) {
    if (values.length < MIN_SAMPLES) continue;
    const ratio = Math.min(Math.max(median(values), CLAMP[0]), CLAMP[1]);
    out[category] = { ratio: Math.round(ratio * 100) / 100, samples: values.length };
  }
  return out;
}

/** Hint for the add-quest form, or null when the estimate is already realistic. */
export function estimateHint(cal: Calibration, category: string, estimate: number): string | null {
  const c = cal[category];
  if (!c || Math.abs(c.ratio - 1) < 0.15 || !(estimate > 0)) return null;
  const suggested = Math.max(5, Math.round((estimate * c.ratio) / 5) * 5);
  return `You usually take about ${c.ratio}× your estimate for ${category} — about ${suggested} min.`;
}
