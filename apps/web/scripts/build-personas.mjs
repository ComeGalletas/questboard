// Bundles the persona packs in /personas for the static web build:
//   src/generated/personas.json            manifests + fallback lines
//   public/personas/<slug>/{sprite,portrait}.png
// Outputs are gitignored and rebuilt before dev/build/test/typecheck.
// Full pack validation lives in the runner (`python -m runner packs`); here a pack without its
// manifest, fallback lines or sprite is skipped, and the sprite's frame count is recorded so a
// short sheet shows idle for the missing states.
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
  const missing = ["persona.yaml", "lines.fallback.json", "assets/sprite.png"].filter(
    (f) => !existsSync(join(dir, f)),
  );
  if (missing.length > 0) {
    console.warn(`skipped persona pack ${entry.name}: missing ${missing.join(", ")}`);
    continue;
  }
  const manifest = parse(await readFile(join(dir, "persona.yaml"), "utf8"));
  const { lines } = JSON.parse(await readFile(join(dir, "lines.fallback.json"), "utf8"));
  await mkdir(join(publicDir, entry.name), { recursive: true });
  const assets = { frames: spriteFrames(await readFile(join(dir, "assets", "sprite.png"))) };
  for (const name of ["sprite", "portrait"]) {
    const src = join(dir, "assets", `${name}.png`);
    if (!existsSync(src)) continue;
    await copyFile(src, join(publicDir, entry.name, `${name}.png`));
    assets[name] = `/personas/${entry.name}/${name}.png`;
  }
  packs.push({ ...manifest, assets, lines });
}
/** Frames in a row of 32x32 frames, from the PNG header; capped at the five states. */
function spriteFrames(png) {
  const isPng = png.length >= 24 && png.readUInt32BE(0) === 0x89504e47;
  const width = isPng ? png.readUInt32BE(16) : 0;
  return Math.min(5, Math.max(1, Math.floor(width / 32)));
}

await mkdir(dirname(outFile), { recursive: true });
await writeFile(outFile, JSON.stringify(packs, null, 2) + "\n");
console.log(`bundled ${packs.length} persona packs`);
