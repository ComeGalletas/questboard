import { test } from "node:test";
import assert from "node:assert/strict";
import { applyAction, finishTiming } from "./actions.ts";
import { at, quest } from "./fixtures.ts";

const now = at("2026-09-25", 10);

test("complete on the scheduled day is on time with full XP", () => {
  const r = applyAction(quest({ xp: 40 }), { kind: "complete", actualMin: 35 }, now);
  assert.ok(r.ok);
  assert.equal(r.trigger, "completed_on_time");
  assert.equal(r.patch.status, "done");
  assert.equal(r.patch.actual_min, 35);
  assert.equal(r.patch.xp_awarded, 40);
  assert.equal(r.patch.completed_at, now.toISOString());
});

test("timing uses the deadline when there is one", () => {
  const deadline = at("2026-09-27", 9).toISOString();
  assert.equal(finishTiming({ deadline, scheduled_for: null }, now), "early");
  assert.equal(finishTiming({ deadline, scheduled_for: null }, at("2026-09-27", 8)), "on_time");
  assert.equal(finishTiming({ deadline, scheduled_for: null }, at("2026-09-27", 10)), "late");
});

test("without a deadline the scheduled day decides", () => {
  const q = { deadline: null, scheduled_for: "2026-09-25" };
  assert.equal(finishTiming(q, at("2026-09-24")), "early");
  assert.equal(finishTiming(q, at("2026-09-25", 23)), "on_time");
  assert.equal(finishTiming(q, at("2026-09-26", 0, 1)), "late");
  assert.equal(finishTiming({ deadline: null, scheduled_for: null }, now), "on_time");
});

test("late completion and partial reduce XP", () => {
  const late = applyAction(
    quest({ xp: 40 }),
    { kind: "complete", actualMin: 50 },
    at("2026-09-26"),
  );
  assert.ok(late.ok);
  assert.equal(late.trigger, "completed_late");
  assert.equal(late.patch.xp_awarded, 30);
  const partial = applyAction(quest({ xp: 40 }), { kind: "partial", actualMin: 15 }, now);
  assert.ok(partial.ok);
  assert.equal(partial.trigger, "partial");
  assert.equal(partial.patch.status, "partial");
  assert.equal(partial.patch.xp_awarded, 20);
});

test("start, snooze, defer, skip", () => {
  const started = applyAction(quest(), { kind: "start" }, now);
  assert.ok(started.ok);
  assert.equal(started.patch.status, "in_progress");
  assert.equal(started.trigger, "started");

  const snoozed = applyAction(quest(), { kind: "snooze", minutes: 30 }, now);
  assert.ok(snoozed.ok);
  assert.equal(snoozed.patch.snoozed_until, new Date(now.getTime() + 30 * 60_000).toISOString());

  const deferred = applyAction(quest(), { kind: "defer", to: "2026-09-27" }, now);
  assert.ok(deferred.ok);
  assert.deepEqual(deferred.patch, {
    status: "deferred",
    scheduled_for: "2026-09-27",
    snoozed_until: null,
  });

  const skipped = applyAction(quest(), { kind: "skip" }, now);
  assert.ok(skipped.ok);
  assert.equal(skipped.trigger, "skipped");
});

test("invalid actions are refused", () => {
  assert.equal(applyAction(quest({ status: "done" }), { kind: "skip" }, now).ok, false);
  assert.equal(applyAction(quest({ status: "in_progress" }), { kind: "start" }, now).ok, false);
  assert.equal(applyAction(quest(), { kind: "defer", to: "2026-09-25" }, now).ok, false);
  assert.equal(applyAction(quest(), { kind: "snooze", minutes: 0 }, now).ok, false);
  assert.equal(applyAction(quest(), { kind: "complete", actualMin: -1 }, now).ok, false);
});
