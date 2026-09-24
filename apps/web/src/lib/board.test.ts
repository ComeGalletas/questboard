import { test } from "node:test";
import assert from "node:assert/strict";
import { boardRange } from "./board.ts";

test("today is a single date", () => {
  assert.deepEqual(boardRange("today", new Date(2026, 8, 25, 23, 30)), {
    from: "2026-09-25",
    to: "2026-09-25",
  });
});

test("week runs Monday to Sunday", () => {
  const range = { from: "2026-09-21", to: "2026-09-27" };
  assert.deepEqual(boardRange("week", new Date(2026, 8, 21)), range); // Monday
  assert.deepEqual(boardRange("week", new Date(2026, 8, 27)), range); // Sunday
});

test("month covers the calendar month", () => {
  assert.deepEqual(boardRange("month", new Date(2026, 1, 10)), {
    from: "2026-02-01",
    to: "2026-02-28",
  });
});
