// Applying and describing setup-assistant config patches (pure). A patch replaces whole
// top-level keys; the user reviews the before/after and applies it.

import type { Config, ConfigPatch } from "@questboard/schema";

export const PATCH_KEYS = [
  "timezone",
  "goals",
  "capacity",
  "quiet_hours",
  "persona_order",
] as const;

export function applyPatch(config: Config, patch: ConfigPatch): Config {
  const next: Config = { ...config };
  for (const key of PATCH_KEYS) {
    const value = patch[key];
    if (value !== undefined && value !== null)
      (next as unknown as Record<string, unknown>)[key] = value;
  }
  return next;
}

function show(key: (typeof PATCH_KEYS)[number], value: unknown): string {
  if (value === undefined || value === null) return "—";
  switch (key) {
    case "goals":
      return (
        (value as Config["goals"]).map((g) => `${g.title} (${g.horizon})`).join(", ") || "none"
      );
    case "capacity": {
      const c = value as Config["capacity"];
      return `${c.weekday_hours} h weekdays, ${c.weekend_hours} h weekends, focus ${Math.round(c.focus_factor * 100)} %`;
    }
    case "quiet_hours": {
      const q = value as Config["quiet_hours"];
      return `${q.start}–${q.end}`;
    }
    case "persona_order":
      return (value as string[]).join(" → ");
    default:
      return String(value);
  }
}

export type PatchLine = { key: string; before: string; after: string };

export function describePatch(config: Config, patch: ConfigPatch): PatchLine[] {
  return PATCH_KEYS.filter((k) => patch[k] !== undefined && patch[k] !== null)
    .map((k) => ({
      key: k.replace("_", " "),
      before: show(k, config[k]),
      after: show(k, patch[k]),
    }))
    .filter((l) => l.before !== l.after);
}
