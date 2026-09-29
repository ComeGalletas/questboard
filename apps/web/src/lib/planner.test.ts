import { test } from "node:test";
import assert from "node:assert/strict";
import { emptyPlanNotice, type PlanRun } from "./planner.ts";

const TUESDAY = new Date(2026, 8, 29, 9, 0);

function run(over: Partial<PlanRun>): PlanRun {
  return {
    job: "weekly",
    date: "2026-09-27", // Sunday: plans Sep 28 - Oct 4
    ops_count: 0,
    summary: "Both goals already have open quests.",
    finished_at: "2026-09-29T13:00:00Z",
    ...over,
  };
}

test("an empty weekly run shows its summary on the week board", () => {
  assert.deepEqual(emptyPlanNotice("week", [run({})], TUESDAY), {
    text: "The planner proposed nothing this week.",
    summary: "Both goals already have open quests.",
  });
  assert.equal(emptyPlanNotice("today", [run({})], TUESDAY), null);
  assert.equal(emptyPlanNotice("month", [run({})], TUESDAY), null);
});

test("runs with ops, older runs without a count and other periods show nothing", () => {
  assert.equal(emptyPlanNotice("week", [run({ ops_count: 3 })], TUESDAY), null);
  assert.equal(emptyPlanNotice("week", [run({ ops_count: null })], TUESDAY), null);
  assert.equal(emptyPlanNotice("week", [run({ date: "2026-09-20" })], TUESDAY), null);
});

test("the most recent success wins (a forced re-run replaces the empty one)", () => {
  const forced = run({ ops_count: 2, finished_at: "2026-09-29T14:00:00Z" });
  assert.equal(emptyPlanNotice("week", [run({}), forced], TUESDAY), null);
  const emptyAgain = run({ summary: null, finished_at: "2026-09-29T15:00:00Z" });
  assert.deepEqual(emptyPlanNotice("week", [forced, emptyAgain], TUESDAY), {
    text: "The planner proposed nothing this week.",
    summary: null,
  });
});

test("daily_am and monthly match today and the current month", () => {
  const am = run({ job: "daily_am", date: "2026-09-29" });
  assert.equal(
    emptyPlanNotice("today", [am], TUESDAY)?.text,
    "The planner proposed nothing for today.",
  );
  const month = run({ job: "monthly", date: "2026-09-01" });
  assert.equal(
    emptyPlanNotice("month", [month], TUESDAY)?.text,
    "The planner proposed nothing this month.",
  );
  assert.equal(emptyPlanNotice("month", [month], new Date(2026, 9, 2)), null);
});
