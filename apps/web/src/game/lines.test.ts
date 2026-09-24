import { test } from "node:test";
import assert from "node:assert/strict";
import { actualVsEstimate, fill, formatDuration, selectLine, type Candidate } from "./lines.ts";

const line = (over: Partial<Candidate>): Candidate => ({
  trigger: "completed_on_time",
  condition: "any",
  variant: 1,
  text: "Done.",
  ...over,
});
const first = () => 0;

test("cache wins over fallback; mood-specific wins over any", () => {
  const cached = [
    line({ text: "any", id: "a" }),
    line({ text: "pleased", condition: "pleased", id: "b" }),
  ];
  const fallback = [line({ text: "fallback" })];
  const pick = selectLine({
    trigger: "completed_on_time",
    mood: "pleased",
    cached,
    fallback,
    random: first,
  });
  assert.deepEqual(pick, { text: "pleased", id: "b", source: "cache" });
  const neutral = selectLine({
    trigger: "completed_on_time",
    mood: "neutral",
    cached,
    fallback,
    random: first,
  });
  assert.equal(neutral?.text, "any");
});

test("falls back to pack lines when the cache has nothing for the trigger", () => {
  const pick = selectLine({
    trigger: "skipped",
    mood: "neutral",
    cached: [line({})],
    fallback: [line({ trigger: "skipped", text: "Fine. Tomorrow." })],
  });
  assert.deepEqual(pick, { text: "Fine. Tomorrow.", source: "fallback" });
  assert.equal(
    selectLine({ trigger: "abandoned", mood: "neutral", cached: [], fallback: [] }),
    null,
  );
});

test("no-repeat: unused lines first, then the least recently used", () => {
  const cached = [
    line({ text: "old", used_at: "2026-09-20T10:00:00Z" }),
    line({ text: "older", used_at: "2026-09-01T10:00:00Z" }),
  ];
  assert.equal(
    selectLine({ trigger: "completed_on_time", mood: "neutral", cached, fallback: [] })?.text,
    "older",
  );
  cached.push(line({ text: "fresh" }));
  assert.equal(
    selectLine({ trigger: "completed_on_time", mood: "neutral", cached, fallback: [] })?.text,
    "fresh",
  );
});

test("lines with placeholders we cannot fill are skipped", () => {
  const cached = [line({ text: "{streak} days strong!" }), line({ text: "Nice work." })];
  const noStreak = selectLine({
    trigger: "completed_on_time",
    mood: "neutral",
    cached,
    fallback: [],
    random: first,
  });
  assert.equal(noStreak?.text, "Nice work.");
  const withStreak = selectLine({
    trigger: "completed_on_time",
    mood: "neutral",
    cached: [cached[0]],
    fallback: [],
    values: { streak: "4" },
  });
  assert.equal(withStreak?.text, "4 days strong!");
});

test("placeholder helpers", () => {
  assert.equal(fill("{next_quest} is next", { next_quest: "Stretch" }), "Stretch is next");
  assert.equal(formatDuration(45), "45 min");
  assert.equal(formatDuration(120), "2 h");
  assert.equal(formatDuration(135), "2 h 15 min");
  assert.equal(actualVsEstimate(31, 30), "right on estimate");
  assert.equal(actualVsEstimate(50, 30), "20 min over");
  assert.equal(actualVsEstimate(10, 30), "20 min under");
});
