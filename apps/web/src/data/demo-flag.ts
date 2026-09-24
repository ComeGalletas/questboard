const FLAG = "questboard.demo";

export function demoEnabled(): boolean {
  try {
    return localStorage.getItem(FLAG) === "1";
  } catch {
    return false;
  }
}

const listeners = new Set<() => void>();

/** For useSyncExternalStore: null on the server / during hydration. */
export function subscribeDemo(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function setDemo(on: boolean): void {
  try {
    if (on) localStorage.setItem(FLAG, "1");
    else localStorage.removeItem(FLAG);
  } catch {
    // storage unavailable
  }
  for (const fn of listeners) fn();
}
