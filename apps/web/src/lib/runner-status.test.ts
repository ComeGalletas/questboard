import { test } from "node:test";
import assert from "node:assert/strict";
import { OFFLINE_AFTER_MS, formatAge, runnerStatus, statusLabel } from "./runner-status.ts";

const now = new Date("2026-09-25T12:00:00Z");
const ago = (ms: number) => new Date(now.getTime() - ms).toISOString();

test("no heartbeat is offline, never seen", () => {
  const s = runnerStatus(null, now);
  assert.deepEqual(s, { kind: "offline", lastSeenMs: null });
  assert.equal(statusLabel(s), "Runner offline · never seen");
});

test("recent heartbeat is online", () => {
  assert.equal(runnerStatus(ago(4 * 60_000), now).kind, "online");
  assert.equal(runnerStatus(ago(OFFLINE_AFTER_MS), now).kind, "online");
});

test("heartbeat older than three ticks is offline with age", () => {
  const s = runnerStatus(ago(OFFLINE_AFTER_MS + 1), now);
  assert.equal(s.kind, "offline");
  assert.equal(statusLabel(runnerStatus(ago(3 * 3_600_000), now)), "Runner offline · seen 3 h ago");
});

test("clock skew into the future counts as just seen", () => {
  assert.deepEqual(runnerStatus(ago(-60_000), now), { kind: "online", lastSeenMs: 0 });
});

test("garbage timestamps are offline", () => {
  assert.equal(runnerStatus("not a date", now).kind, "offline");
});

test("formatAge buckets", () => {
  assert.equal(formatAge(30_000), "just now");
  assert.equal(formatAge(5 * 60_000), "5 min ago");
  assert.equal(formatAge(47 * 3_600_000), "47 h ago");
  assert.equal(formatAge(72 * 3_600_000), "3 d ago");
});
