"use client";

// Desktop shell only: shows released PC notifications as Windows toasts, once each, and has the
// persona react. The runner decides when a notification is released (quiet hours, dedup).

import { useEffect } from "react";
import { useLog } from "@/data/log";
import { useReaction } from "@/data/reaction";
import { companionSay, isDesktop, showNotification } from "@/lib/desktop";
import { MAX_AGE_MS, pcDue, spriteForKind, toastFor } from "@/lib/pc-notifications";

export function PcNotifier() {
  const { store } = useLog();
  const { react } = useReaction();

  useEffect(() => {
    if (!isDesktop() || store.kind !== "supabase") return;
    const handled = new Set<string>();
    let stopped = false;
    let running = false;
    let again = false;

    const check = async () => {
      if (running) {
        again = true;
        return;
      }
      running = true;
      try {
        do {
          again = false;
          const now = new Date();
          const rows = await store.listPcNotifications(
            new Date(now.getTime() - 2 * MAX_AGE_MS).toISOString(),
          );
          const { show, skip } = pcDue(rows, now, handled);
          const done = [...show, ...skip];
          if (!done.length) continue;
          done.forEach((n) => handled.add(n.id));
          // Stamp first: a notification must never show twice, even if a toast fails.
          await store.markPcShown(
            done.map((n) => n.id),
            now.toISOString(),
          );
          for (const n of show) {
            if (stopped) return;
            const toast = toastFor(n);
            await showNotification(toast).catch(() => {});
            if (n.persona) {
              const cue = {
                persona: n.persona,
                text: toast.body || toast.title,
                state: spriteForKind(n.kind),
              };
              react(cue);
              await companionSay(cue).catch(() => {}); // the overlay says it too
            }
          }
        } while (again && !stopped);
      } catch {
        // Offline or signed out: the next change or reload tries again.
      } finally {
        running = false;
      }
    };

    void check();
    const unsubscribe = store.subscribeNotifications(() => void check());
    return () => {
      stopped = true;
      unsubscribe();
    };
  }, [store, react]);

  return null;
}
