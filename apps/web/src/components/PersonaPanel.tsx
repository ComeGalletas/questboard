"use client";

import { useMemo } from "react";
import type { Summary } from "@/game/summary";
import { isQuietHours } from "@/game/summary";
import { selectLine, type Placeholders } from "@/game/lines";
import type { Trigger } from "@/game/actions";
import { packFor } from "@/game/personas";
import { useLog } from "@/data/log";
import { spriteStateFor, useReaction } from "@/data/reaction";
import { useNow } from "@/lib/hooks";
import { DialogueBox } from "@/ui/DialogueBox";
import { Sprite } from "@/ui/Sprite";
import { timeLeft } from "./useQuestActions";

/** Deterministic pick so the idle line doesn't change on every render. */
function seeded(seed: string): () => number {
  let h = 2166136261;
  for (const c of seed) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return () => ((h >>> 0) % 1000) / 1000;
}

function idleTrigger(summary: Summary, hour: number): Trigger {
  if (summary.trigger) return summary.trigger;
  if (hour < 12) return "reminder_am";
  if (hour < 17) return "reminder_mid";
  return "reminder_pm";
}

export function PersonaPanel({ summary }: { summary: Summary }) {
  const { lines, config } = useLog();
  const { reaction } = useReaction();
  const now = useNow(60_000);
  const hour = now.getHours();
  const quiet = isQuietHours(config.quiet_hours, now);

  const idle = useMemo(() => {
    const trigger = idleTrigger(summary, hour);
    const values: Placeholders = {
      time_left: summary.next ? timeLeft(summary.next, new Date()) : undefined,
      streak: summary.streak.days > 0 ? String(summary.streak.days) : undefined,
      next_quest: summary.next?.title,
    };
    const picked = selectLine({
      trigger,
      mood: summary.mood,
      cached: lines.filter((l) => !l.quest_id && l.persona === summary.speaker),
      fallback: packFor(summary.speaker)?.lines ?? [],
      values,
      random: seeded(`${summary.speaker}:${trigger}:${hour}`),
    });
    return picked ? { trigger, text: picked.text } : null;
  }, [summary, hour, lines]);

  const slug = reaction?.persona ?? summary.speaker;
  const pack = packFor(slug);
  const state =
    quiet && !reaction
      ? "sleep"
      : reaction
        ? reaction.state
        : idle && summary.trigger
          ? spriteStateFor(idle.trigger)
          : "idle";
  const text = reaction?.text ?? (quiet ? "Zzz… (quiet hours)" : idle?.text);

  return (
    <section className="panel persona-panel" aria-label="Persona">
      <Sprite
        sheet={pack?.assets.sprite}
        frames={pack?.assets.frames}
        state={state}
        scale={3}
        label={`${pack?.name ?? slug}, ${state}`}
      />
      {text && (
        <DialogueBox speaker={pack?.name ?? slug} text={text} accent={pack?.accent ?? "#5a5580"} />
      )}
    </section>
  );
}
