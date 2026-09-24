import { test } from "node:test";
import assert from "node:assert/strict";
import { PACKS, packFor, personaForCategory } from "./personas.ts";

test("built-in packs are bundled with sprites and fallback lines", () => {
  for (const slug of ["coach", "teacher", "mom", "quartermaster"]) {
    const pack = packFor(slug);
    assert.ok(pack, slug);
    assert.equal(pack.assets.sprite, `/personas/${slug}/sprite.png`);
    assert.ok(pack.lines.length >= 44);
  }
  assert.ok(PACKS.length >= 4);
});

test("category owners decide the default persona", () => {
  const order = ["coach", "teacher", "mom", "quartermaster"];
  assert.equal(personaForCategory("utilities", order), "quartermaster");
  assert.equal(personaForCategory("learning", order), "teacher");
  assert.equal(personaForCategory("general", order), "coach");
  assert.equal(personaForCategory("general", ["mom", "coach"]), "mom");
});
