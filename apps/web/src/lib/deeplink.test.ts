import { test } from "node:test";
import assert from "node:assert/strict";
import { targetToPath } from "./deeplink.ts";

test("notification targets map to app paths", () => {
  assert.equal(targetToPath("questboard://today"), "/today");
  assert.equal(targetToPath("questboard://week"), "/week");
  assert.equal(
    targetToPath("questboard://quest/5b0e4c1e-2f5a-4d59-9b1a-3f0d3c8b7a10"),
    "/today?quest=5b0e4c1e-2f5a-4d59-9b1a-3f0d3c8b7a10",
  );
  assert.equal(targetToPath("https://evil.example"), "/today");
  assert.equal(targetToPath("questboard://quest/../../x"), "/today");
});
