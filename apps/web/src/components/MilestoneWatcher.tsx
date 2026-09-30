"use client";

// Celebrates milestones (P2, pure code; game/milestones.ts): when the quest log changes, new
// milestones are recorded in milestones_reached, and the freshest one gets a persona line on the
// board (and in the desktop companion). Old ones, e.g. from before this device saw them, are
// recorded quietly so nothing floods in at once.

import { useEffect, useRef } from "react";
import { useLog } from "@/data/log";
import { useReaction } from "@/data/reaction";
import { selectMilestoneLine } from "@/game/lines";
import { detectMilestones, newMilestones } from "@/game/milestones";
import { packFor } from "@/game/personas";
import { summarize } from "@/game/summary";
import { companionSay } from "@/lib/desktop";

export function MilestoneWatcher() {
  const { store, quests, config, lines, loaded } = useLog();
  const { react } = useReaction();
  const known = useRef<Set<string> | null>(null);
  const busy = useRef(false);

  useEffect(() => {
    if (!loaded || busy.current) return;
    busy.current = true;
    void (async () => {
      try {
        if (!known.current)
          known.current = new Set((await store.listReachedMilestones()).map((r) => r.key));
        const now = new Date();
        const { celebrate, quiet } = newMilestones(
          detectMilestones(quests, now),
          known.current,
          now,
        );
        const fresh = [...celebrate, ...quiet];
        if (!fresh.length) return;
        await store.recordMilestones(
          fresh.map((r) => ({
            key: r.key,
            milestone: r.milestone,
            label: r.label,
            reached_at: r.at.toISOString(),
          })),
        );
        fresh.forEach((r) => known.current!.add(r.key));

        const top = celebrate[0];
        if (!top) return;
        const summary = summarize(quests, config, "today", now);
        const persona = top.persona ?? summary.speaker;
        const picked = selectMilestoneLine({
          milestone: top.milestone,
          mood: "pleased",
          cached: lines.filter((l) => l.persona === persona),
          fallback: packFor(persona)?.lines ?? [],
          values: { milestone: top.label, ...top.values },
        });
        if (!picked) return;
        const cue = { persona, text: picked.text, state: "happy" as const };
        react(cue);
        await companionSay(cue).catch(() => {});
      } catch {
        // Offline or signed out: the next change tries again.
      } finally {
        busy.current = false;
      }
    })();
  }, [loaded, quests, config, lines, store, react]);

  return null;
}
