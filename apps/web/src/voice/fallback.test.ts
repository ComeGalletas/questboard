import { test } from "node:test";
import assert from "node:assert/strict";
import type { VoiceCommand } from "@questboard/schema";
import type { LiveRequest } from "../data/store.ts";
import { VOICE_TTL_MS, fallbackOutcome, fallbackRequest } from "./fallback.ts";

const req = (over: Partial<LiveRequest<VoiceCommand>>): LiveRequest<VoiceCommand> => ({
  status: "pending",
  result: null,
  error: null,
  ...over,
});

test("the request carries the trimmed utterance, language and local day", () => {
  assert.deepEqual(fallbackRequest("  apunta lo del gimnasio  ", "es", "2026-09-30"), {
    utterance: "apunta lo del gimnasio",
    lang: "es",
    today: "2026-09-30",
  });
  assert.equal(fallbackRequest("x".repeat(400), "en", "2026-09-30").utterance.length, 300);
});

test("waiting says whether the PC is on", () => {
  assert.deepEqual(fallbackOutcome(req({}), 0, 1000, false), {
    kind: "waiting",
    text: "Asking your PC's runner to interpret it…",
  });
  assert.match(fallbackOutcome(req({ status: "running" }), 0, 1000, true).kind, /waiting/);
  const offline = fallbackOutcome(req({}), 0, 1000, true);
  assert.equal(offline.kind === "waiting" && offline.text.includes("when the PC is on"), true);
});

test("an answer becomes a command for the confirmation card", () => {
  const command: VoiceCommand = { intent: "create", lang: "es", title: "Llamar a Ana" };
  assert.deepEqual(fallbackOutcome(req({ status: "done", result: command }), 0, 1000, false), {
    kind: "command",
    command,
  });
});

test("failures, a swept row and a long wait all end the wait", () => {
  assert.equal(fallbackOutcome(req({ status: "failed" }), 0, 1000, false).kind, "failed");
  assert.equal(fallbackOutcome(req({ status: "cancelled" }), 0, 1000, false).kind, "failed");
  assert.equal(fallbackOutcome(null, 0, 1000, false).kind, "failed");
  assert.equal(fallbackOutcome(req({}), 0, VOICE_TTL_MS + 1, true).kind, "failed");
});
