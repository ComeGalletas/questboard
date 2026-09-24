"use client";

import { useCallback, useState } from "react";
import type { Quest } from "@questboard/schema";
import { applyAction, type QuestAction } from "@/game/actions";
import { actualVsEstimate, formatDuration, selectLine, type Placeholders } from "@/game/lines";
import type { Mood } from "@/game/progress";
import { streak } from "@/game/progress";
import { packFor } from "@/game/personas";
import { useLog } from "@/data/log";
import { spriteStateFor, useReaction } from "@/data/reaction";
import { endOfLocalDay, isoDate } from "@/game/dates";

export function timeLeft(q: Quest, now: Date): string {
  const due = q.deadline ? new Date(q.deadline) : endOfLocalDay(q.scheduled_for ?? isoDate(now));
  return formatDuration((due.getTime() - now.getTime()) / 60_000);
}

/** Applies an action (P2, instant), persists it, and makes the quest's persona react. */
export function useQuestActions(mood: Mood, next: Quest | null) {
  const { store, quests, lines, reload } = useLog();
  const { react } = useReaction();
  const [error, setError] = useState<string | null>(null);

  const act = useCallback(
    async (quest: Quest, action: QuestAction) => {
      const now = new Date();
      const result = applyAction(quest, action, now);
      if (!result.ok) {
        setError(result.reason);
        return false;
      }
      setError(null);
      try {
        await store.updateQuest(quest.id, result.patch);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        return false;
      }
      const after = quests.map((q) => (q.id === quest.id ? { ...q, ...result.patch } : q));
      const days = streak(after, now).days;
      const values: Placeholders = {
        time_left: timeLeft(quest, now),
        streak: days > 0 ? String(days) : undefined,
        days_carried: quest.carries > 0 ? String(quest.carries) : undefined,
        actual_vs_estimate:
          result.patch.actual_min != null
            ? actualVsEstimate(result.patch.actual_min, quest.estimate_min)
            : undefined,
        next_quest: next && next.id !== quest.id ? next.title : undefined,
      };
      const pack = packFor(quest.persona);
      const picked = selectLine({
        trigger: result.trigger,
        mood,
        cached: lines.filter((l) => l.quest_id === quest.id && l.persona === quest.persona),
        fallback: pack?.lines ?? [],
        values,
      });
      if (picked) {
        react({
          persona: quest.persona,
          trigger: result.trigger,
          text: picked.text,
          state: spriteStateFor(result.trigger),
        });
        if (picked.id) void store.markLineUsed(picked.id, now.toISOString());
      }
      await reload();
      return true;
    },
    [store, quests, lines, reload, react, mood, next],
  );

  return { act, error, clearError: () => setError(null) };
}
