// Generates src/generated/*.ts from schemas/*.schema.json. Do not edit the output by hand.
import { readdir, writeFile, mkdir } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { compileFromFile } from "json-schema-to-typescript";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const schemaDir = join(root, "schemas");
const outDir = join(root, "src", "generated");
const banner = "/* Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`. */";

await mkdir(outDir, { recursive: true });
const files = (await readdir(schemaDir)).filter((f) => f.endsWith(".schema.json")).sort();
const exports = [];
for (const file of files) {
  const name = file.replace(".schema.json", "");
  const ts = await compileFromFile(join(schemaDir, file), {
    cwd: schemaDir,
    bannerComment: banner,
    additionalProperties: false,
    style: { singleQuote: false },
  });
  await writeFile(join(outDir, `${name}.ts`), ts);
  exports.push(`export type * from "./${name}";`);
}
await writeFile(join(outDir, "index.ts"), `${banner}\n${exports.join("\n")}\n`);
