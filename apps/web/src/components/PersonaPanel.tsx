"use client";

import { useMemo } from "react";
import type { Summary } from "@/game/summary";
import { idleCue, isQuietHours } from "@/game/summary";
import { selectLine, type Placeholders } from "@/game/lines";
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

export function PersonaPanel({ summary }: { summary: Summary }) {
  const { lines, config } = useLog();
  const { reaction } = useReaction();
  const now = useNow(60_000);
  const hour = now.getHours();
  const quiet = isQuietHours(config.quiet_hours, now);

  const idle = useMemo(() => {
    const { trigger, quest } = idleCue(summary, hour);
    // A forgotten quest's own persona speaks, from that quest's cached lines.
    const speaker = quest?.persona ?? summary.speaker;
    const focus = quest ?? summary.next;
    const values: Placeholders = {
      time_left: focus ? timeLeft(focus, new Date()) : undefined,
      streak: summary.streak.days > 0 ? String(summary.streak.days) : undefined,
      days_carried: quest && quest.carries > 0 ? String(quest.carries) : undefined,
      next_quest: focus?.title,
    };
    const picked = selectLine({
      trigger,
      mood: summary.mood,
      cached: lines.filter(
        (l) => l.persona === speaker && (quest ? l.quest_id === quest.id : !l.quest_id),
      ),
      fallback: packFor(speaker)?.lines ?? [],
      values,
      random: seeded(`${speaker}:${trigger}:${hour}`),
    });
    return picked ? { trigger, speaker, text: picked.text } : null;
  }, [summary, hour, lines]);

  const slug = reaction?.persona ?? idle?.speaker ?? summary.speaker;
  const pack = packFor(slug);
  const state =
    quiet && !reaction
      ? "sleep"
      : reaction
        ? reaction.state
        : idle && !idle.trigger.startsWith("reminder_")
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
