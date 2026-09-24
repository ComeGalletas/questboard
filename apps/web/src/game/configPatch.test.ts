import { test } from "node:test";
import assert from "node:assert/strict";
import { DEMO_CONFIG } from "../data/demo-store.ts";
import { applyPatch, describePatch } from "./configPatch.ts";

const patch = {
  goals: [{ id: "10k", title: "Run a 10k", horizon: "quarter" as const, persona: "coach" }],
  capacity: { weekday_hours: 2, weekend_hours: 4, focus_factor: 0.8 },
  timezone: "America/Bogota",
};

test("a patch replaces whole keys and leaves the rest alone", () => {
  const next = applyPatch(DEMO_CONFIG, patch);
  assert.deepEqual(next.goals, patch.goals);
  assert.deepEqual(next.capacity, patch.capacity);
  assert.deepEqual(next.llm, DEMO_CONFIG.llm);
});

test("the review lists only real changes", () => {
  assert.deepEqual(describePatch(DEMO_CONFIG, patch), [
    { key: "goals", before: "none", after: "Run a 10k (quarter)" },
    {
      key: "capacity",
      before: "3 h weekdays, 5 h weekends, focus 70 %",
      after: "2 h weekdays, 4 h weekends, focus 80 %",
    },
  ]);
});
