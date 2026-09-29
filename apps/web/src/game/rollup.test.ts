import { test } from "node:test";
import assert from "node:assert/strict";
import { applyAction, finishTiming } from "./actions.ts";
import { at, quest } from "./fixtures.ts";
import { periodEnd, rollup, turnInXp } from "./rollup.ts";
import { boardRows } from "./summary.ts";

// The first real week: "Gym: 4 sessions of 1 hour or more", 300 min, worked through daily steps.
const MONDAY = "2026-09-28";
const gym = quest({
  title: "Gym",
  cadence: "weekly",
  scheduled_for: MONDAY,
  estimate_min: 300,
  xp: 300,
});
const step = (day: string, over: Parameters<typeof quest>[0] = {}) =>
  quest({ title: "Gym session", parent_id: gym.id, scheduled_for: day, estimate_min: 60, ...over });
const done = (day: string, actual: number, xp = 60) =>
  step(day, {
    status: "done",
    actual_min: actual,
    xp_awarded: xp,
    completed_at: at(day, 19).toISOString(),
  });

test("a parent without steps has no roll-up", () => {
  assert.equal(rollup(gym, [gym, quest()]), null);
});

test("finished steps advance the parent by logged minutes; open steps don't", () => {
  const log = [gym, done(MONDAY, 70), step("2026-09-30", { status: "partial", actual_min: 30 })];
  log.push(step("2026-10-01"), step("2026-09-29", { status: "skipped" }));
  assert.deepEqual(rollup(gym, log), {
    done: 2,
    total: 4,
    open: 1,
    doneMin: 100,
    targetMin: 300,
    earnedXp: 60,
    ready: false,
  });
});

test("steps without logged time count their estimate", () => {
  const r = rollup(gym, [gym, step(MONDAY, { status: "done", actual_min: null })]);
  assert.equal(r?.doneMin, 60);
});

test("ready to turn in once the steps cover the target and none is open", () => {
  const four = ["2026-09-28", "2026-09-29", "2026-10-01", "2026-10-03"].map((d) => done(d, 75));
  assert.equal(rollup(gym, [gym, ...four])?.ready, true);
  // Every step done but short of the target (the planner adds steps a day at a time): not yet.
  assert.equal(rollup(gym, [gym, done(MONDAY, 60)])?.ready, false);
  // Target reached but a step is still open: not yet either.
  assert.equal(rollup(gym, [gym, ...four, step("2026-10-04")])?.ready, false);
});

test("turning in a parent pays what its steps haven't, with a floor", () => {
  assert.equal(turnInXp(300, 300, 0), 300);
  assert.equal(turnInXp(300, 300, 120), 180);
  assert.equal(turnInXp(300, 300, 290), 60); // 20 % turn-in bonus
  const r = applyAction(gym, { kind: "complete", actualMin: 300 }, at("2026-10-03"), 240);
  assert.ok(r.ok);
  assert.equal(r.patch.xp_awarded, 60);
  assert.equal(r.trigger, "completed_on_time");
});

test("weekly and monthly quests are due at the end of their period", () => {
  assert.equal(periodEnd(gym), "2026-10-04");
  assert.equal(periodEnd({ cadence: "monthly", scheduled_for: "2026-02-01" }), "2026-02-28");
  assert.equal(periodEnd({ cadence: "daily", scheduled_for: MONDAY }), MONDAY);
  // Before this fix a weekly quest finished on Wednesday counted as late (due Monday night).
  assert.equal(finishTiming(gym, at("2026-09-30")), "on_time");
  assert.equal(finishTiming(gym, at("2026-10-04", 23)), "on_time");
  assert.equal(finishTiming(gym, at("2026-10-05", 9)), "late");
});

test("board rows carry the roll-up and the step's parent", () => {
  const s = done(MONDAY, 70);
  const log = [gym, s];
  const [week] = boardRows(log, "week", at("2026-09-29"));
  assert.equal(week.quest.id, gym.id);
  assert.equal(week.progress?.doneMin, 70);
  assert.equal(week.parent, null);
  const [today] = boardRows(log, "today", at(MONDAY));
  assert.equal(today.parent?.id, gym.id);
  assert.equal(today.progress, null);
});
