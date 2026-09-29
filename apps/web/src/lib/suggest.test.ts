import { test } from "node:test";
import assert from "node:assert/strict";
import { suggestState } from "./suggest.ts";

test("waiting says whether the PC runner is offline", () => {
  assert.equal(suggestState(null, false).text, "Asking the planner…");
  assert.match(suggestState(null, true).text, /Waiting for your PC's runner/);
  const running = { status: "running" as const, result: null, error: null };
  assert.equal(suggestState(running, false).text, "The planner is working…");
});

test("done reports how many suggestions arrived", () => {
  const done = (ops_count: number | null) => ({
    status: "done" as const,
    result: { status: "succeeded" as const, reason: "ok", ops_count },
    error: null,
  });
  assert.equal(suggestState(done(0), false).text, "The planner proposed nothing new.");
  assert.equal(suggestState(done(1), false).text, "1 new suggestion above.");
  assert.equal(suggestState(done(3), false).text, "3 new suggestions above.");
});

test("failures carry the runner's reason", () => {
  const failed = { status: "failed" as const, result: null, error: "gave up after 10 attempts" };
  assert.deepEqual(suggestState(failed, false), {
    kind: "error",
    text: "The planner couldn't run: gave up after 10 attempts.",
  });
  const expired = { status: "cancelled" as const, result: null, error: "expired" };
  assert.equal(suggestState(expired, false).kind, "error");
});
