import { test } from "node:test";
import assert from "node:assert/strict";
import { deletionFor, deletionMessage, editFormFor, editPatch } from "./edit.ts";
import { endOfLocalDay } from "./dates.ts";
import { quest } from "./fixtures.ts";

test("an unchanged form patches nothing", () => {
  const q = quest({ deadline: endOfLocalDay("2026-10-01").toISOString() });
  assert.deepEqual(editPatch(q, editFormFor(q)), { ok: true, patch: {} });
});

test("only changed fields are patched, and XP follows while the quest is open", () => {
  const q = quest({ title: "Gym", estimate_min: 30, priority: 2, xp: 30 });
  const f = { ...editFormFor(q), title: "  Gym, legs  ", estimate: "60", priority: 1 };
  const r = editPatch(q, f);
  assert.equal(r.ok, true);
  assert.deepEqual(r.ok && r.patch, {
    title: "Gym, legs",
    estimate_min: 60,
    priority: 1,
    xp: r.ok ? r.patch.xp : 0,
  });
  assert.ok(r.ok && r.patch.xp! > 30, "higher estimate and priority are worth more");
});

test("a finished quest keeps the XP it was worth", () => {
  const q = quest({ status: "done", xp: 30, xp_awarded: 30 });
  const r = editPatch(q, { ...editFormFor(q), estimate: "90" });
  assert.deepEqual(r, { ok: true, patch: { estimate_min: 90 } });
});

test("day and deadline", () => {
  const q = quest({ scheduled_for: "2026-09-25", deadline: null });
  const r = editPatch(q, { ...editFormFor(q), day: "2026-09-27", deadline: "2026-10-02" });
  assert.deepEqual(r, {
    ok: true,
    patch: {
      scheduled_for: "2026-09-27",
      deadline: endOfLocalDay("2026-10-02").toISOString(),
    },
  });
  const cleared = quest({ deadline: endOfLocalDay("2026-10-02").toISOString() });
  assert.deepEqual(editPatch(cleared, { ...editFormFor(cleared), deadline: "" }), {
    ok: true,
    patch: { deadline: null },
  });
});

test("invalid edits are refused with a reason", () => {
  const q = quest();
  const bad = (over: object) => editPatch(q, { ...editFormFor(q), ...over });
  assert.deepEqual(bad({ title: "   " }), { ok: false, reason: "Title must be 1–120 characters" });
  assert.equal(bad({ estimate: "0" }).ok, false);
  assert.equal(bad({ estimate: "12.5" }).ok, false);
  assert.equal(bad({ estimate: "2000" }).ok, false);
  assert.equal(bad({ day: "" }).ok, false, "a scheduled quest keeps a day");
});

test("deleting a quest takes its steps and says what it costs", () => {
  const parent = quest({ title: "Gym: 4 sessions", cadence: "weekly", xp_awarded: null });
  const s1 = quest({ parent_id: parent.id, status: "done", xp_awarded: 15 });
  const s2 = quest({ parent_id: parent.id });
  const other = quest();
  const d = deletionFor(parent, [parent, s1, s2, other]);
  assert.deepEqual(d.ids, [s1.id, s2.id, parent.id], "steps first, then the quest");
  assert.equal(d.earnedXp, 15);
  assert.equal(
    deletionMessage(parent, d),
    "Delete “Gym: 4 sessions”? Its 2 steps go too. The 15 XP earned is removed. This can't be undone.",
  );
  assert.equal(
    deletionMessage(other, deletionFor(other, [other])),
    `Delete “${other.title}”? This can't be undone.`,
  );
});
