import { test } from "node:test";
import assert from "node:assert/strict";
import { frameIndex } from "./sprite-frames.ts";

test("states map to their frame; missing frames fall back to idle", () => {
  assert.equal(frameIndex("happy"), 2);
  assert.equal(frameIndex("sleep", 5), 4);
  assert.equal(frameIndex("talk", 2), 1);
  assert.equal(frameIndex("happy", 2), 0);
  assert.equal(frameIndex("sleep", 1), 0);
});
