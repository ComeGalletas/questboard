"use client";

import type { Summary } from "@/game/summary";
import { DialogueBox } from "@/ui/DialogueBox";
import { Sprite } from "@/ui/Sprite";
import { usePersonaCue } from "./usePersonaCue";

export function PersonaPanel({ summary }: { summary: Summary }) {
  const { slug, pack, state, text } = usePersonaCue(summary);

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
