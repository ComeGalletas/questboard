import { test } from "node:test";
import assert from "node:assert/strict";
import type { QuestProposal } from "@questboard/schema";
import { DEMO_CONFIG } from "../data/demo-store.ts";
import { describe, planAcceptance } from "./proposals.ts";
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
