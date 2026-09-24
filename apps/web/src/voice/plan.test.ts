import { test } from "node:test";
import assert from "node:assert/strict";
import { quest } from "../game/fixtures.ts";
import { parseCommand } from "./grammar.ts";
import {
  actionFrom,
  draftFor,
  draftProblem,
  newQuestFrom,
  type CreateDraft,
  type QuestDraft,
} from "./plan.ts";

const TODAY = "2026-09-24";
const CONFIG = { persona_order: ["coach", "teacher", "mom", "quartermaster"], xp_weights: {} };
const laundry = quest({ id: "q1", title: "Do the laundry", estimate_min: 45 });
const bank = quest({ id: "q2", title: "Call the bank" });
const mom = quest({ id: "q3", title: "Call mom" });
const done = quest({ id: "q4", title: "Laundry sorting", status: "done" });
const QUESTS = [laundry, bank, mom, done];

function draft(text: string) {
  return draftFor(parseCommand(text, TODAY), QUESTS, CONFIG, TODAY);
}

test("create: the milestone phrase becomes a voice quest with a deadline at the said time", () => {
  const d = draft("create task visit grandma next Saturday at ten") as CreateDraft;
  assert.deepEqual(
    { title: d.title, date: d.date, time: d.time, persona: d.persona, estimate: d.estimate },
    { title: "Visit grandma", date: "2026-09-26", time: "10:00", persona: "coach", estimate: 30 },
  );
  assert.equal(draftProblem(d, TODAY), null);
  const q = newQuestFrom(d, CONFIG);
  assert.equal(q.source, "voice");
  assert.equal(q.scheduled_for, "2026-09-26");
  assert.equal(q.category, "general");
  const deadline = new Date(q.deadline!);
  assert.deepEqual([deadline.getDate(), deadline.getHours(), deadline.getMinutes()], [26, 10, 0]);

  const plain = draft("add buy milk") as CreateDraft;
  assert.equal(plain.date, TODAY);
  assert.equal(newQuestFrom(plain, CONFIG).deadline, null);
  assert.equal(draftProblem({ ...plain, title: " " }, TODAY), "Say or type a title");
  assert.equal(draftProblem({ ...plain, date: "2026-09-01" }, TODAY), "Pick today or a later day");
});

test("quest commands match open quests only and preselect a unique match", () => {
  const c = draft("complete laundry") as QuestDraft;
  assert.equal(c.questId, "q1");
  assert.equal(c.minutes, 45); // actual time defaults to the estimate
  assert.deepEqual(
    c.candidates.map((q) => q.id),
    ["q1", "q2", "q3"],
  );
  assert.deepEqual(actionFrom(c), { kind: "complete", actualMin: 45 });

  const s = draft("snooze call for 20 minutes") as QuestDraft;
  assert.equal(s.questId, null); // ambiguous: the user picks
  assert.deepEqual(s.candidates.map((q) => q.id).slice(0, 2), ["q2", "q3"]);
  assert.equal(draftProblem(s, TODAY), "Pick the quest");
  assert.deepEqual(actionFrom({ ...s, questId: "q2" }), { kind: "snooze", minutes: 20 });

  const d = draft("defer the bank to Monday") as QuestDraft;
  assert.equal(d.questId, "q2");
  assert.deepEqual(actionFrom(d), { kind: "defer", to: "2026-09-28" });
  assert.equal(draftProblem({ ...d, date: TODAY }, TODAY), "Defer needs a later day");

  const noDate = draft("defer the bank") as QuestDraft;
  assert.equal(noDate.date, "2026-09-25");
});

test("everything else needs no quest", () => {
  assert.deepEqual(draft("what's next"), { kind: "whats_next" });
  assert.deepEqual(draft("tell me a joke"), { kind: "unknown" });
});
