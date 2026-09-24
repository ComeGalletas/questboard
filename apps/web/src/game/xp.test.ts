import { test } from "node:test";
import assert from "node:assert/strict";
import { awardedXp, baseXp, levelForXp, levelProgress, xpForLevel } from "./xp.ts";

test("base XP follows estimate, priority and category weight", () => {
  assert.equal(baseXp({ estimate_min: 30, priority: 2, category: "general" }), 30);
  assert.equal(baseXp({ estimate_min: 30, priority: 1, category: "general" }), 45);
  assert.equal(baseXp({ estimate_min: 40, priority: 3, category: "general" }), 30);
  assert.equal(baseXp({ estimate_min: 30, priority: 2, category: "health" }, { health: 2 }), 60);
  assert.equal(baseXp({ estimate_min: 1, priority: 3, category: "general" }), 5);
});

test("finish modifiers", () => {
  assert.equal(awardedXp(40, "early"), 44);
  assert.equal(awardedXp(40, "on_time"), 40);
  assert.equal(awardedXp(40, "late"), 30);
  assert.equal(awardedXp(40, "partial"), 20);
});

test("levels grow triangularly", () => {
  assert.deepEqual([1, 2, 3, 4].map(xpForLevel), [0, 100, 300, 600]);
  assert.equal(levelForXp(0), 1);
  assert.equal(levelForXp(99), 1);
  assert.equal(levelForXp(100), 2);
  assert.equal(levelForXp(650), 4);
  assert.deepEqual(levelProgress(350), { level: 3, into: 50, span: 300 });
});
