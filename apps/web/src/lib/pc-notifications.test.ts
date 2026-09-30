import { test } from "node:test";
import assert from "node:assert/strict";
import type { Notification } from "@questboard/schema";
import { MAX_TOASTS, pcDue, spriteForKind, toastFor } from "./pc-notifications.ts";

const NOW = new Date("2026-09-30T14:00:00Z");
const hoursAgo = (h: number) => new Date(NOW.getTime() - h * 3_600_000).toISOString();

function note(id: string, over: Partial<Notification> = {}): Notification {
  return {
    id,
    kind: "quest_due",
    target: "questboard://today",
    persona: "coach",
    dedup_date: "2026-09-30",
    channels: ["pc", "push"],
    title: "Due soon",
    body: "Gym session",
    sent_at: hoursAgo(1),
    pc_shown_at: null,
    created_at: hoursAgo(2),
    ...over,
  };
}

test("shows released PC notifications once, newest first", () => {
  const rows = [
    note("a", { sent_at: hoursAgo(3) }),
    note("b", { sent_at: hoursAgo(1) }),
    note("held", { sent_at: null }), // still in quiet hours
    note("phone-only", { channels: ["push"] }),
    note("shown", { pc_shown_at: hoursAgo(1) }),
  ];
  const { show, skip } = pcDue(rows, NOW, new Set());
  assert.deepEqual(
    show.map((n) => n.id),
    ["b", "a"],
  );
  assert.deepEqual(skip, []);
  assert.deepEqual(
    pcDue(rows, NOW, new Set(["b"])).show.map((n) => n.id),
    ["a"],
    "handled this session",
  );
});

test("old or excess notifications are marked shown without a toast", () => {
  const rows = [
    note("stale", { sent_at: hoursAgo(13) }),
    ...Array.from({ length: MAX_TOASTS + 2 }, (_, i) =>
      note(`n${i}`, { sent_at: hoursAgo(i * 0.1) }),
    ),
  ];
  const { show, skip } = pcDue(rows, NOW, new Set());
  assert.deepEqual(
    show.map((n) => n.id),
    ["n0", "n1", "n2"],
  );
  assert.deepEqual(skip.map((n) => n.id).sort(), ["n3", "n4", "stale"]);
});

test("toast text falls back per kind and respects the DB limits", () => {
  assert.deepEqual(toastFor(note("x", { kind: "week_ready", title: null, body: null })), {
    title: "This week's plan is ready",
    body: "",
    target: "questboard://today",
  });
  assert.equal(toastFor(note("y", { title: "t".repeat(100) })).title.length, 80);
});

test("sprite state per kind", () => {
  assert.equal(spriteForKind("day_recap"), "happy");
  assert.equal(spriteForKind("quest_overdue"), "concerned");
  assert.equal(spriteForKind("streak_risk"), "concerned");
  assert.equal(spriteForKind("day_ready"), "talk");
  assert.equal(spriteForKind("persona_speech"), "talk");
});
