// Generates src/generated/index.ts from schemas/*.schema.json. Do not edit the output by hand.
// All schemas are compiled through one root so shared definitions are emitted exactly once.
import { readdir, writeFile, mkdir, rm } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const schemaDir = join(root, "schemas");
const outDir = join(root, "src", "generated");
const banner = "/* Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`. */";

const files = (await readdir(schemaDir)).filter((f) => f.endsWith(".schema.json")).sort();
const bundle = {
  title: "QuestboardSchemas",
  type: "object",
  additionalProperties: false,
  properties: Object.fromEntries(files.map((f) => [f.replace(".schema.json", ""), { $ref: f }])),
};
const ts = await compile(bundle, "QuestboardSchemas", {
  cwd: schemaDir,
  bannerComment: banner,
  additionalProperties: false,
  unreachableDefinitions: true,
  // Array length limits are enforced by JSON Schema / Pydantic, not by TS tuple types.
  ignoreMinAndMaxItems: true,
  style: { singleQuote: false },
});
await rm(outDir, { recursive: true, force: true });
await mkdir(outDir, { recursive: true });
await writeFile(join(outDir, "index.ts"), ts);
