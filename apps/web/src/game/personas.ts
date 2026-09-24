// Installed persona packs, bundled at build time from /personas (see scripts/build-personas.mjs).

import type { FallbackLine, PersonaPack } from "@questboard/schema";
import bundled from "../generated/personas.json" with { type: "json" };

export type Pack = PersonaPack & {
  /** frames: how many of the five sprite states the sheet has (missing ones show idle). */
  assets: { sprite?: string; portrait?: string; frames: number };
  lines: FallbackLine[];
};

export const PACKS = bundled as Pack[];

export function packFor(slug: string): Pack | undefined {
  return PACKS.find((p) => p.slug === slug);
}

/** Default persona for a category: an owner (highest priority), else the first in order. */
export function personaForCategory(category: string, order: string[]): string {
  const owners = PACKS.filter((p) => p.owns.includes(category as PersonaPack["owns"][number]));
  if (owners.length > 0) return [...owners].sort((a, b) => b.priority - a.priority)[0].slug;
  return order.find((slug) => packFor(slug)) ?? PACKS[0]?.slug ?? "coach";
}
