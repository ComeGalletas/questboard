import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { FallbackLine } from "@questboard/schema";
import { at, quest } from "./fixtures.ts";
import { selectMilestoneLine } from "./lines.ts";
import { DETECTORS, detectMilestones, newMilestones, type Reached } from "./milestones.ts";

const done = (day: string, over = {}) =>
  quest({
    status: "done",
    scheduled_for: day,
    completed_at: at(day, 10).toISOString(),
    xp_awarded: 30,
    ...over,
  });

test("the registry covers every milestone id in the shared schema", () => {
  const common = JSON.parse(
    readFileSync(
      new URL("../../../../packages/schema/schemas/common.schema.json", import.meta.url),
      "utf-8",
    ),
  );
  assert.deepEqual(Object.keys(DETECTORS).sort(), [...common.$defs.MilestoneId.enum].sort());
});

test("streaks: the highest step of the current run, keyed by the run's first day", () => {
  const days = [
    "2026-09-24",
    "2026-09-25",
    "2026-09-26",
    "2026-09-27",
    "2026-09-28",
    "2026-09-29",
    "2026-09-30",
  ];
  const quests = days.map((d) => done(d));
  const [r] = DETECTORS.streak(quests, at("2026-09-30", 20));
  assert.equal(r.key, "streak:7:2026-09-24");
  assert.equal(r.label, "7-day streak");
  assert.equal(r.values?.streak, "7");
  assert.equal(r.at.getTime(), at("2026-09-30", 12).getTime(), "reached on the 7th day");
  assert.deepEqual(DETECTORS.streak(quests.slice(0, 2), at("2026-09-25", 20)), [], "under 3");
});

test("levels: each level reached, dated by the finish that crossed it", () => {
  const quests = [
    done("2026-09-20", { xp_awarded: 60 }),
    done("2026-09-21", { xp_awarded: 60 }), // 120 -> level 2
    done("2026-09-22", { xp_awarded: 200 }), // 320 -> level 3
  ];
  const levels = DETECTORS.level_up(quests, at("2026-09-22", 20));
  assert.deepEqual(
    levels.map((r) => [r.key, r.label]),
    [
      ["level:2", "Level 2"],
      ["level:3", "Level 3"],
    ],
  );
  assert.equal(levels[1].at.toISOString(), at("2026-09-22", 10).toISOString());
});

test("period quests: a finished weekly quest, cheered by its own persona", () => {
  const weekly = done("2026-09-28", {
    cadence: "weekly",
    title: "Gym: 4 sessions",
    persona: "coach",
  });
  const [r] = DETECTORS.period_done([weekly, done("2026-09-28")], at("2026-09-30"));
  assert.equal(r.label, "Gym: 4 sessions done");
  assert.equal(r.persona, "coach");
  assert.equal(r.key, `period_done:${weekly.id}`);
});

test("perfect week: last Mon–Sun, every daily done and none forgotten", () => {
  const week = ["2026-09-21", "2026-09-22", "2026-09-24", "2026-09-27"].map((d) => done(d));
  const monday = at("2026-09-29"); // Tuesday of the next week
  assert.equal(DETECTORS.perfect_week(week, monday)[0]?.key, "perfect_week:2026-09-21");
  const missed = [...week, quest({ scheduled_for: "2026-09-23", status: "skipped" })];
  assert.deepEqual(DETECTORS.perfect_week(missed, monday), []);
  const forgot = [
    ...week.slice(1),
    done("2026-09-21", { forgotten_on: ["2026-09-20", "2026-09-22"] }),
  ];
  assert.deepEqual(DETECTORS.perfect_week(forgot, monday), [], "a forgotten day spoils it");
  assert.deepEqual(DETECTORS.perfect_week(week.slice(0, 2), monday), [], "too few quests");
});

test("only fresh milestones are celebrated; old ones are recorded quietly", () => {
  const now = at("2026-09-30", 20);
  const r = (key: string, when: Date): Reached => ({
    milestone: "level_up",
    key,
    label: key,
    at: when,
  });
  const reached = [
    r("level:2", at("2026-09-01")),
    r("level:3", at("2026-09-30", 9)),
    r("level:4", at("2026-09-30", 18)),
  ];
  const { celebrate, quiet } = newMilestones(reached, new Set(["level:4"]), now);
  assert.deepEqual(
    celebrate.map((x) => x.key),
    ["level:3"],
  );
  assert.deepEqual(
    quiet.map((x) => x.key),
    ["level:2"],
  );
  assert.ok(detectMilestones([], now).length === 0);
});

test("a milestone's own line first, then the generic one with {milestone}", () => {
  const fallback: FallbackLine[] = [
    { trigger: "milestone", variant: 1, condition: "any", text: "Big moment: {milestone}." },
    {
      trigger: "milestone",
      milestone: "streak",
      variant: 1,
      condition: "any",
      text: "{streak} days straight!",
    },
  ];
  const pick = (milestone: "streak" | "level_up") =>
    selectMilestoneLine({
      milestone,
      mood: "neutral",
      cached: [],
      fallback,
      values: { milestone: milestone === "streak" ? "7-day streak" : "Level 3", streak: "7" },
      random: () => 0,
    })?.text;
  assert.equal(pick("streak"), "7 days straight!");
  assert.equal(pick("level_up"), "Big moment: Level 3.");
  const cached = [
    {
      trigger: "milestone" as const,
      milestone: "level_up" as const,
      condition: "any" as const,
      variant: 1,
      text: "Fresh: {milestone}!",
    },
  ];
  assert.equal(
    selectMilestoneLine({
      milestone: "level_up",
      mood: "neutral",
      cached,
      fallback,
      values: { milestone: "Level 3" },
    })?.text,
    "Fresh: Level 3!",
  );
});
