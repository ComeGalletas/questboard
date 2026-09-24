import { test } from "node:test";
import assert from "node:assert/strict";
import { DEMO_CONFIG } from "../data/demo-store.ts";
import { boardRows, isQuietHours, summarize } from "./summary.ts";
import { at, quest } from "./fixtures.ts";

const now = at("2026-09-25", 10);

test("today shows this day's quests plus unsettled carry-overs, closed last", () => {
  const qs = [
    quest({ title: "done", status: "done", completed_at: now.toISOString() }),
    quest({ title: "p1", priority: 1 }),
    quest({ title: "p2" }),
    quest({ title: "old open", scheduled_for: "2026-09-23" }),
    quest({ title: "old done", scheduled_for: "2026-09-23", status: "done" }),
    quest({ title: "tomorrow", scheduled_for: "2026-09-26" }),
    quest({ title: "weekly", cadence: "weekly" }),
    quest({ title: "doing", status: "in_progress" }),
    quest({
      title: "napping",
      status: "snoozed",
      snoozed_until: at("2026-09-25", 11).toISOString(),
    }),
  ];
  const rows = boardRows(qs, "today", now);
  assert.deepEqual(
    rows.map((r) => r.quest.title),
    ["doing", "p1", "p2", "old open", "napping", "done"],
  );
  assert.equal(rows.find((r) => r.quest.title === "old open")?.carriedFrom, "2026-09-23");
});

test("an expired snooze is active again", () => {
  const q = quest({ status: "snoozed", snoozed_until: at("2026-09-25", 9).toISOString() });
  assert.equal(boardRows([q], "today", now)[0].snoozed, false);
});

test("week board has the week's weekly quests only", () => {
  const qs = [
    quest({ title: "w", cadence: "weekly", scheduled_for: "2026-09-21" }),
    quest({ title: "last week", cadence: "weekly", scheduled_for: "2026-09-14" }),
    quest({ title: "d" }),
  ];
  assert.deepEqual(
    boardRows(qs, "week", now).map((r) => r.quest.title),
    ["w"],
  );
});

test("quiet hours wrap midnight", () => {
  const q = { start: "22:00", end: "07:00" };
  assert.equal(isQuietHours(q, at("2026-09-25", 23)), true);
  assert.equal(isQuietHours(q, at("2026-09-25", 6, 59)), true);
  assert.equal(isQuietHours(q, at("2026-09-25", 7)), false);
  assert.equal(isQuietHours({ start: "13:00", end: "14:00" }, at("2026-09-25", 13, 30)), true);
});

test("summary picks the busiest persona as speaker and the next quest", () => {
  const qs = [
    quest({ persona: "mom", title: "a" }),
    quest({ persona: "mom", title: "b", priority: 1 }),
    quest({ persona: "coach", title: "c" }),
  ];
  const s = summarize(qs, DEMO_CONFIG, "today", now);
  assert.equal(s.speaker, "mom");
  assert.equal(s.next?.title, "b");
  assert.equal(s.mood, "neutral");
  assert.equal(s.level.level, 1);
});
