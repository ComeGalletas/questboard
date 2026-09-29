import { test } from "node:test";
import assert from "node:assert/strict";
import { KINDS, notifyTestState } from "./notify-test.ts";

test("the picker offers every notification kind, day_ready first", () => {
  assert.equal(KINDS[0], "day_ready");
  assert.equal(KINDS.length, 11);
});

test("waiting says whether the PC runner is offline", () => {
  assert.match(notifyTestState(null, true).text, /Waiting for your PC's runner/);
  assert.equal(notifyTestState(null, false).text, "Asking your PC's runner to send it…");
  const running = { status: "running" as const, result: null, error: null };
  assert.equal(notifyTestState(running, false).kind, "waiting");
});

test("done lists each device's outcome", () => {
  const done = {
    status: "done" as const,
    error: null,
    result: {
      kind: "day_ready" as const,
      target: "questboard://today",
      devices: [
        { device: "iPhone, web app (a1b2c3d4)", outcome: "sent" as const },
        { device: "Windows, Edge (e5f6a7b8)", outcome: "removed" as const, error: null },
        {
          device: "Android, Chrome (c9d0e1f2)",
          outcome: "failed" as const,
          error: "push failed (403)",
        },
      ],
    },
  };
  assert.deepEqual(notifyTestState(done, false), {
    kind: "done",
    text: "Test sent to 1 of 3 devices.",
    devices: [
      "iPhone, web app (a1b2c3d4): sent",
      "Windows, Edge (e5f6a7b8): expired endpoint removed",
      "Android, Chrome (c9d0e1f2): failed (push failed (403))",
    ],
  });
  const none = { ...done, result: { ...done.result, devices: [done.result.devices[2]] } };
  assert.equal(notifyTestState(none, false).kind, "error");
  assert.equal(notifyTestState(none, false).text, "Test sent to 0 of 1 device.");
});

test("failures carry the runner's reason", () => {
  const failed = {
    status: "failed" as const,
    result: null,
    error: "QUESTBOARD_VAPID_PRIVATE_KEY is not set on the runner PC",
  };
  assert.deepEqual(notifyTestState(failed, false), {
    kind: "error",
    text: "Not sent: QUESTBOARD_VAPID_PRIVATE_KEY is not set on the runner PC.",
    devices: [],
  });
  const expired = { status: "cancelled" as const, result: null, error: "expired" };
  assert.equal(notifyTestState(expired, false).kind, "error");
});
