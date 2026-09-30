// Bridge to the Tauri desktop shell (apps/desktop). The shell sets window.__TAURI__
// (withGlobalTauri), so the web app needs no Tauri packages; in a browser everything here is a
// no-op.

type TauriGlobal = {
  core: { invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> };
  event: { listen<T>(event: string, handler: (e: { payload: T }) => void): Promise<() => void> };
};

function tauri(): TauriGlobal | null {
  if (typeof window === "undefined") return null;
  return (window as unknown as { __TAURI__?: TauriGlobal }).__TAURI__ ?? null;
}

/** Shows a Windows toast; clicking it opens `target` (a questboard:// link) in the app. */
export async function showNotification(toast: {
  title: string;
  body: string;
  target: string;
}): Promise<void> {
  await tauri()?.core.invoke("show_notification", toast);
}

/** True inside the desktop shell. */
export function isDesktop(): boolean {
  return tauri() !== null;
}

/**
 * Calls `open` with each questboard:// link the shell receives: one that launched the app, and
 * any opened while it runs. The shell keeps only the latest link; taking it clears it.
 * Returns an unsubscribe function.
 */
export function onDeepLink(open: (target: string) => void): () => void {
  const t = tauri();
  if (!t) return () => {};
  let stopped = false;
  let unlisten: (() => void) | null = null;
  const take = () => {
    void t.core.invoke<string | null>("take_deep_link").then((target) => {
      if (target && !stopped) open(target);
    });
  };
  void t.event.listen("deep-link", take).then((stop) => {
    if (stopped) stop();
    else unlisten = stop;
  });
  take();
  return () => {
    stopped = true;
    unlisten?.();
  };
}
