// Bundles the persona packs in /personas for the static web build:
//   src/generated/personas.json            manifests + fallback lines
//   public/personas/<slug>/{sprite,portrait}.png
// Outputs are gitignored and rebuilt before dev/build/test/typecheck.
import { copyFile, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const packsDir = join(web, "..", "..", "personas");
const publicDir = join(web, "public", "personas");
const outFile = join(web, "src", "generated", "personas.json");

await rm(publicDir, { recursive: true, force: true });
const packs = [];
for (const entry of (await readdir(packsDir, { withFileTypes: true })).sort((a, b) =>
  a.name.localeCompare(b.name),
)) {
  if (!entry.isDirectory()) continue;
  const dir = join(packsDir, entry.name);
  const manifest = parse(await readFile(join(dir, "persona.yaml"), "utf8"));
  const { lines } = JSON.parse(await readFile(join(dir, "lines.fallback.json"), "utf8"));
  await mkdir(join(publicDir, entry.name), { recursive: true });
  const assets = {};
  for (const name of ["sprite", "portrait"]) {
    const src = join(dir, "assets", `${name}.png`);
    if (!existsSync(src)) continue;
    await copyFile(src, join(publicDir, entry.name, `${name}.png`));
    assets[name] = `/personas/${entry.name}/${name}.png`;
  }
  packs.push({ ...manifest, assets, lines });
}
await mkdir(dirname(outFile), { recursive: true });
await writeFile(outFile, JSON.stringify(packs, null, 2) + "\n");
console.log(`bundled ${packs.length} persona packs`);
