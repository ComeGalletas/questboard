// Which open quest a spoken name means ("complete laundry" -> "Do the laundry"). Pure code (P2);
// mirrors runner/runner/voice/match.py, both locked to packages/schema/fixtures/voice.json.

import { normalize } from "./grammar.ts";

export type QuestMatch =
  { kind: "match"; id: string } | { kind: "ambiguous"; ids: string[] } | { kind: "none" };

const STOPWORDS = new Set(
  (
    "the a an my to of and for task quest " +
    "el la los las lo un una mi mis de del al y tarea mision"
  ).split(" "),
);

function words(s: string): string[] {
  return normalize(s)
    .split(/[^a-z0-9ñ]+/)
    .filter((w) => w && !STOPWORDS.has(w));
}

/** Same word, or one a prefix of the other (impuesto / impuestos) once both have 4+ letters. */
function same(a: string, b: string): boolean {
  if (a === b) return true;
  return Math.min(a.length, b.length) >= 4 && (a.startsWith(b) || b.startsWith(a));
}

const MIN_SCORE = 0.5;

/** Score = share of the spoken words found in the title; the best unique score >= 0.5 wins. */
export function matchQuest(ref: string, quests: { id: string; title: string }[]): QuestMatch {
  const said = words(ref);
  if (said.length === 0) return { kind: "none" };
  let best = 0;
  let ids: string[] = [];
  for (const q of quests) {
    const title = words(q.title);
    const hits = said.filter((w) => title.some((t) => same(w, t))).length;
    const score = hits / said.length;
    if (score < MIN_SCORE) continue;
    if (score > best) {
      best = score;
      ids = [q.id];
    } else if (score === best) {
      ids.push(q.id);
    }
  }
  if (ids.length === 0) return { kind: "none" };
  return ids.length === 1 ? { kind: "match", id: ids[0] } : { kind: "ambiguous", ids };
}
