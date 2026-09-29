import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { isDesktop, onDeepLink } from "./desktop.ts";

const g = globalThis as { window?: unknown };

afterEach(() => {
  delete g.window;
});

function fakeShell(pending: string[]) {
  const listeners: Array<() => void> = [];
  let unlistened = 0;
  g.window = {
    __TAURI__: {
      core: {
        invoke: async (cmd: string) =>
          cmd === "take_deep_link" ? (pending.shift() ?? null) : null,
      },
      event: {
        listen: async (_event: string, handler: () => void) => {
          listeners.push(handler);
          return () => unlistened++;
        },
      },
    },
  };
  return { fire: () => listeners.forEach((l) => l()), unlistened: () => unlistened };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

test("outside the shell: not desktop, and deep links are a no-op", () => {
  assert.equal(isDesktop(), false);
  const stop = onDeepLink(() => assert.fail("no links outside the shell"));
  stop();
});

test("takes the link that launched the app, then each one the shell announces", async () => {
  const pending = ["questboard://week"];
  const shell = fakeShell(pending);
  assert.equal(isDesktop(), true);
  const opened: string[] = [];
  const stop = onDeepLink((t) => opened.push(t));
  await tick();
  assert.deepEqual(opened, ["questboard://week"]);

  pending.push("questboard://today");
  shell.fire();
  await tick();
  assert.deepEqual(opened, ["questboard://week", "questboard://today"]);

  stop();
  assert.equal(shell.unlistened(), 1);
  pending.push("questboard://month");
  shell.fire();
  await tick();
  assert.equal(opened.length, 2, "nothing opens after unsubscribing");
});
