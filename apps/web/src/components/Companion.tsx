"use client";

// The desktop companion overlay (a transparent, always-on-top window): the lead persona's
// sprite, a speech bubble when it has something to say, and a quick menu on click. The window
// is click-through except the elements marked data-hit, whose boxes are sent to the shell.

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useLog } from "@/data/log";
import { useReaction } from "@/data/reaction";
import { summarize } from "@/game/summary";
import {
  dragCompanion,
  hideCompanion,
  onCompanionSay,
  openDashboard,
  setCompanionHitAreas,
} from "@/lib/desktop";
import { useNow } from "@/lib/hooks";
import { DialogueBox } from "@/ui/DialogueBox";
import { Sprite } from "@/ui/Sprite";
import { usePersonaCue } from "./usePersonaCue";

/** Pointer travel (px) that turns a press on the sprite into a drag instead of a click. */
const DRAG_PX = 4;

export function Companion() {
  const { quests, config } = useLog();
  const { react } = useReaction();
  const now = useNow(60_000);
  const summary = useMemo(() => summarize(quests, config, "today", now), [quests, config, now]);
  const { slug, pack, state, text, quiet, reacting } = usePersonaCue(summary);
  const [menu, setMenu] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const press = useRef<{ x: number; y: number; dragged: boolean } | null>(null);

  // The dashboard forwards its reactions (PC notifications) here.
  useEffect(() => onCompanionSay((cue) => react(cue)), [react]);

  // Tell the shell which boxes take the pointer; everything else clicks through.
  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const report = () => {
      const areas = [...el.querySelectorAll<HTMLElement>("[data-hit]")].map((n) => {
        const r = n.getBoundingClientRect();
        return { x: r.left, y: r.top, width: r.width, height: r.height };
      });
      void setCompanionHitAreas(areas).catch(() => {});
    };
    report();
    const observer = new ResizeObserver(report);
    el.querySelectorAll("[data-hit]").forEach((n) => observer.observe(n));
    return () => observer.disconnect();
  });

  const speaking = reacting && !quiet && text;
  const name = pack?.name ?? slug;

  function whatsNext() {
    setMenu(false);
    react({
      persona: slug,
      state: "talk",
      text: summary.next ? `Next up: ${summary.next.title}` : "Nothing left on today's board.",
    });
  }

  return (
    <div ref={root} className="companion">
      {speaking && (
        <div data-hit className="companion-bubble">
          <DialogueBox speaker={name} text={text} accent={pack?.accent ?? "#5a5580"} />
        </div>
      )}
      {menu && (
        <nav data-hit className="panel companion-menu" aria-label="Companion menu">
          <button type="button" onClick={() => (setMenu(false), void openDashboard())}>
            Open Questboard
          </button>
          <button type="button" onClick={whatsNext}>
            What&apos;s next
          </button>
          <button type="button" onClick={() => (setMenu(false), void hideCompanion())}>
            Hide companion
          </button>
        </nav>
      )}
      <button
        type="button"
        data-hit
        className="companion-sprite"
        aria-label={`${name}: open the menu (drag to move)`}
        aria-expanded={menu}
        onPointerDown={(e) => {
          press.current = { x: e.clientX, y: e.clientY, dragged: false };
        }}
        onPointerMove={(e) => {
          const p = press.current;
          if (!p || p.dragged || e.buttons !== 1) return;
          if (Math.hypot(e.clientX - p.x, e.clientY - p.y) >= DRAG_PX) {
            p.dragged = true;
            void dragCompanion();
          }
        }}
        onClick={() => {
          if (!press.current?.dragged) setMenu((m) => !m);
          press.current = null;
        }}
      >
        <Sprite
          sheet={pack?.assets.sprite}
          frames={pack?.assets.frames}
          state={state}
          scale={3}
          label={`${name}, ${state}`}
        />
      </button>
    </div>
  );
}
