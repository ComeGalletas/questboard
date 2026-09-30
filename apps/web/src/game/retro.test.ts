import { test } from "node:test";
import assert from "node:assert/strict";
import type { Retro } from "@questboard/schema";
import { retroPatch, retroToShow } from "./retro.ts";

const retro = (over: Partial<Retro> = {}): Retro => ({
  id: "r1",
  cadence: "weekly",
  period_start: "2026-09-21",
  period_end: "2026-09-27",
  questions: [
    { id: "q1", text: "What went well?" },
    { id: "q2", text: "What got in the way?" },
  ],
  answers: null,
  status: "open",
  source: "model",
  answered_at: null,
  created_at: "2026-09-27T23:00:00Z",
  ...over,
});

test("shows the newest open retro while it's recent", () => {
  const older = retro({ id: "old", period_start: "2026-09-14", period_end: "2026-09-20" });
  assert.equal(retroToShow([older, retro()], "2026-09-30")?.id, "r1");
  assert.equal(retroToShow([retro({ status: "answered" })], "2026-09-30"), null);
  assert.equal(retroToShow([retro({ status: "skipped" })], "2026-09-30"), null);
  assert.equal(retroToShow([retro()], "2026-10-07")?.id, "r1", "10 days after the week");
  assert.equal(retroToShow([retro()], "2026-10-08"), null, "then it lapses");
});

test("saves trimmed answers; all blank is a skip", () => {
  const at = new Date("2026-09-30T20:00:00Z");
  assert.deepEqual(retroPatch(retro(), { q1: "  Mornings worked  ", q2: "" }, at), {
    status: "answered",
    answers: [{ id: "q1", answer: "Mornings worked" }],
    answered_at: at.toISOString(),
  });
  assert.deepEqual(retroPatch(retro(), { q1: " ", q2: "" }, at), {
    status: "skipped",
    answers: null,
    answered_at: at.toISOString(),
  });
  assert.equal(retroPatch(retro(), { q1: "x".repeat(600) }, at).answers?.[0].answer.length, 500);
});
