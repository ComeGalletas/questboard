import { test } from "node:test";
import assert from "node:assert/strict";
import type { QuestProposal } from "@questboard/schema";
import { DEMO_CONFIG } from "../data/demo-store.ts";
import { describe, planAcceptance, showsOn } from "./proposals.ts";
import { at, quest } from "./fixtures.ts";

const now = at("2026-09-25", 7);
const proposal = (payload: QuestProposal["payload"]): QuestProposal => ({
  id: "p1",
  op: payload.op,
  payload,
  status: "pending",
  created_at: "2026-09-25T10:30:00Z",
});

test("accepting an add inserts an llm quest with code-computed XP and no deadline", () => {
  const d = planAcceptance(
    proposal({
      op: "add",
      reason: "goal",
      quest: {
        title: "Easy 3 km run",
        persona: "coach",
        cadence: "daily",
        category: "health",
        estimate_min: 25,
        priority: 1,
      },
    }),
    [],
    DEMO_CONFIG,
    now,
  );
  assert.equal(d.kind, "insert");
  if (d.kind !== "insert") return;
  assert.equal(d.quest.source, "llm");
  assert.equal(d.quest.xp, 40); // 25 min x 1.5 (P1), rounded to 5
  assert.equal(d.quest.deadline, null);
  assert.equal(d.quest.scheduled_for, "2026-09-25");
  assert.equal(d.quest.parent_id, null);
});

test("accepted sub-quests keep their parent", () => {
  const parent = quest({ cadence: "weekly" });
  const d = planAcceptance(
    proposal({
      op: "add",
      reason: "split",
      quest: {
        title: "Draft intro",
        persona: "teacher",
        cadence: "daily",
        category: "jobs",
        estimate_min: 30,
        priority: 2,
        scheduled_for: "2026-09-30",
        parent_id: parent.id,
      },
    }),
    [parent],
    DEMO_CONFIG,
    now,
  );
  assert.ok(d.kind === "insert" && d.quest.parent_id === parent.id);
  assert.ok(d.kind === "insert" && d.quest.scheduled_for === "2026-09-30");
});

test("accepting an update patches allowed fields and recomputes XP", () => {
  const q = quest({ estimate_min: 60, xp: 60 });
  const d = planAcceptance(
    proposal({
      op: "update",
      quest_id: q.id,
      reason: "took longer",
      changes: { estimate_min: 90 },
    }),
    [q],
    DEMO_CONFIG,
    now,
  );
  assert.deepEqual(d, { kind: "update", questId: q.id, patch: { estimate_min: 90, xp: 90 } });
});

test("drops and stale targets", () => {
  const q = quest();
  assert.deepEqual(
    planAcceptance(proposal({ op: "drop", quest_id: q.id, reason: "x" }), [q], DEMO_CONFIG, now),
    { kind: "drop", questId: q.id },
  );
  const done = quest({ status: "done", completed_at: now.toISOString() });
  assert.equal(
    planAcceptance(
      proposal({ op: "drop", quest_id: done.id, reason: "x" }),
      [done],
      DEMO_CONFIG,
      now,
    ).kind,
    "stale",
  );
});

test("summaries", () => {
  const q = quest({ title: "Review notes" });
  assert.equal(
    describe(
      proposal({ op: "update", quest_id: q.id, reason: "x", changes: { estimate_min: 45 } }),
      [q],
    ),
    "Change “Review notes”: estimate → 45 min",
  );
  assert.equal(
    describe(proposal({ op: "drop", quest_id: q.id, reason: "x" }), [q]),
    "Drop “Review notes”",
  );
});

test("steps say their day and parent, and show on the parent's board", () => {
  const gym = quest({ title: "Gym", cadence: "weekly", scheduled_for: "2026-09-21" });
  const stepFor = (day: string) =>
    proposal({
      op: "add",
      reason: "breakdown",
      quest: {
        title: "Gym session",
        persona: "coach",
        cadence: "daily",
        category: "health",
        estimate_min: 60,
        priority: 2,
        parent_id: gym.id,
        scheduled_for: day,
      },
    });
  const thursday = stepFor("2026-09-24");
  const today = stepFor("2026-09-25");
  const later = stepFor("2026-09-27");
  assert.equal(describe(thursday, [gym]), "Add “Gym session” (60 min, Thu 09-24) · step of “Gym”");
  assert.equal(describe(thursday, []), "Add “Gym session” (60 min, Thu 09-24)");
  // Week board: every step of the week's plan. Today: only steps due by today.
  for (const p of [today, later]) assert.ok(showsOn(p, [gym], "week", now));
  assert.ok(showsOn(today, [gym], "today", now));
  assert.ok(!showsOn(later, [gym], "today", now));
  assert.ok(!showsOn(later, [gym], "month", now));
  // Plain proposals keep going to their own cadence's board.
  const plain = proposal({ op: "drop", quest_id: gym.id, reason: "x" });
  assert.ok(showsOn(plain, [gym], "week", now) && !showsOn(plain, [gym], "today", now));
});
