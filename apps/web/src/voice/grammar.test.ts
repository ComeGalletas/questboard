import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseCommand, type Lang } from "./grammar.ts";
import { matchQuest } from "./match.ts";

// Shared with the runner parser: both must produce exactly these outputs.
const fixtures = JSON.parse(
  readFileSync(new URL("../../../../packages/schema/fixtures/voice.json", import.meta.url), "utf8"),
);

test("voice grammar matches the shared fixtures", () => {
  for (const f of fixtures.parse as { text: string; hint?: Lang; expect: object }[]) {
    assert.deepEqual(parseCommand(f.text, fixtures.today, f.hint ?? "en"), f.expect, f.text);
  }
});

test("quest matching matches the shared fixtures", () => {
  for (const c of fixtures.match.cases as { ref: string; expect: object }[]) {
    assert.deepEqual(matchQuest(c.ref, fixtures.match.quests), c.expect, c.ref);
  }
});
