// Fails when `pnpm generate` changed or added files that are not in the git index.
import { execFileSync } from "node:child_process";

const paths = ["src/generated", "python/questboard_schema"];
const git = (...args) => execFileSync("git", args, { encoding: "utf8" }).trim();
const changed = git("diff", "--name-only", "--", ...paths);
const untracked = git("ls-files", "--others", "--exclude-standard", "--", ...paths);
const stale = [changed, untracked].filter(Boolean).join("\n");
if (stale) {
  console.error(`Generated schema code is stale; run \`pnpm schema:gen\` and commit:\n${stale}`);
  process.exit(1);
}
