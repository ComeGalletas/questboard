import { test } from "node:test";
import assert from "node:assert/strict";
import {
  boardTrigger,
  capacity,
  completionRate,
  forgottenQuest,
  mood,
  stats,
  streak,
  totalXp,
} from "./progress.ts";
import { at, quest } from "./fixtures.ts";

const done = (date: string, xp = 10, over = {}) =>
  quest({
    status: "done",
    scheduled_for: date,
    completed_at: at(date, 9).toISOString(),
    xp_awarded: xp,
    ...over,
  });

test("XP and stats count finished quests only", () => {
  const qs = [
    done("2026-09-24", 20, { category: "health" }),
    done("2026-09-25", 10, { category: "learning" }),
    quest({ status: "open", xp_awarded: null }),
  ];
  assert.equal(totalXp(qs), 30);
  assert.deepEqual(stats(qs), { discipline: 0, health: 20, career: 10 });
});

test("streak counts back from today, or from yesterday while today is at risk", () => {
  const qs = [done("2026-09-22"), done("2026-09-23"), done("2026-09-24")];
  assert.deepEqual(streak(qs, at("2026-09-25", 8)), { days: 3, atRisk: true });
  assert.deepEqual(streak([...qs, done("2026-09-25")], at("2026-09-25", 20)), {
    days: 4,
    atRisk: false,
  });
  assert.deepEqual(streak(qs, at("2026-09-26")), { days: 0, atRisk: false });
});

test("completion rate and mood", () => {
  const now = at("2026-09-25", 20);
  const qs = [
    done("2026-09-25"),
    done("2026-09-24"),
    quest({ status: "partial", scheduled_for: "2026-09-24", completed_at: now.toISOString() }),
    quest({ status: "skipped", scheduled_for: "2026-09-23" }),
    quest({ status: "open", scheduled_for: "2026-09-25" }), // not settled yet
    done("2026-09-10"), // outside the window
  ];
  assert.deepEqual(completionRate(qs, now), { rate: 2.5 / 4, settled: 4 });
  assert.deepEqual(completionRate([], now), { rate: null, settled: 0 });
  assert.equal(mood(0.8), "pleased");
  assert.equal(mood(0.5), "neutral");
  assert.equal(mood(0.2), "concerned");
  assert.equal(mood(0.1, 2), "neutral");
  assert.equal(mood(null), "neutral");
});

test("forgotten days count as misses for mood while the quest carries open", () => {
  const now = at("2026-09-25", 20);
  const qs = [
    done("2026-09-25"),
    done("2026-09-24"),
    // Forgotten twice, still open on today's board: two missed days, nothing settled today.
    quest({ scheduled_for: "2026-09-25", carries: 2, forgotten_on: ["2026-09-23", "2026-09-24"] }),
    // Forgotten, carried, then done: one miss plus one finish.
    done("2026-09-24", 10, { carries: 1, forgotten_on: ["2026-09-23"] }),
    // Forgotten on the day it hit the cap and was abandoned: one miss, not two.
    quest({ status: "abandoned", scheduled_for: "2026-09-22", forgotten_on: ["2026-09-22"] }),
    quest({ forgotten_on: ["2026-09-10"] }), // outside the window
  ];
  assert.deepEqual(completionRate(qs, now), { rate: 3 / 7, settled: 7 });
  assert.equal(mood(completionRate(qs, now).rate, 7), "neutral");
  // Without the forgotten records the same log reads as a perfect week.
  const clean = qs.map((q) => ({ ...q, forgotten_on: [] }));
  assert.deepEqual(completionRate(clean, now), { rate: 3 / 4, settled: 4 });
  // Streak and XP ignore forgotten days.
  assert.equal(streak(qs, now).days, 2);
  assert.equal(totalXp(qs), totalXp(clean));
});

test("forgottenQuest picks yesterday's forgotten quest until it is touched", () => {
  const morning = at("2026-09-25", 8);
  const low = quest({ title: "low", priority: 3, forgotten_on: ["2026-09-24"] });
  const high = quest({
    title: "high",
    priority: 1,
    status: "overdue",
    forgotten_on: ["2026-09-24"],
  });
  assert.equal(forgottenQuest([low, high], morning)?.title, "high");
  // Started, snoozed or deferred since: no longer called out.
  for (const status of ["in_progress", "snoozed", "deferred", "done"] as const) {
    assert.equal(forgottenQuest([{ ...high, status }], morning), null);
  }
  // Only yesterday's record counts (the lines say "yesterday"); older ones are history.
  assert.equal(forgottenQuest([quest({ forgotten_on: ["2026-09-22"] })], morning), null);
  assert.equal(
    forgottenQuest([quest({ forgotten_on: ["2026-09-25"] })], at("2026-09-25", 22)),
    null,
  );
  assert.equal(
    forgottenQuest([quest({ cadence: "weekly", forgotten_on: ["2026-09-24"] })], morning),
    null,
  );
  assert.equal(forgottenQuest([quest()], morning), null);
});

test("capacity compares open planned effort with focused free time", () => {
  const cfg = { weekday_hours: 2, weekend_hours: 5, focus_factor: 0.5 };
  const friday = at("2026-09-25", 9);
  const qs = [
    quest({ estimate_min: 45 }),
    quest({ estimate_min: 30 }),
    done("2026-09-25", 10, { estimate_min: 90 }),
    quest({ estimate_min: 60, scheduled_for: "2026-09-26" }),
  ];
  assert.deepEqual(capacity(cfg, qs, friday), { availableMin: 60, plannedMin: 75, over: true });
  assert.equal(capacity(cfg, [], at("2026-09-26")).availableMin, 150);
});

test("board triggers", () => {
  const fine = { availableMin: 120, plannedMin: 60, over: false };
  const morning = at("2026-09-25", 11);
  assert.equal(boardTrigger([], fine, morning), null);
  assert.equal(
    boardTrigger([done("2026-09-25"), quest({ status: "skipped" })], fine, morning),
    "all_done",
  );
  assert.equal(boardTrigger([done("2026-09-25"), quest()], fine, morning), "half_by_noon");
  assert.equal(boardTrigger([quest(), quest()], fine, at("2026-09-25", 15)), "nothing_by_15");
  assert.equal(boardTrigger([quest()], { ...fine, over: true }, morning), "over_capacity");
  assert.equal(boardTrigger([quest(), quest()], fine, at("2026-09-25", 13)), null);
});
