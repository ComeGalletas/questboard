"use client";

// What the persona panel is currently saying. Set by quest actions; decays back to idle.

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { Trigger } from "../game/actions";

export type SpriteState = "idle" | "talk" | "happy" | "concerned" | "sleep";

export type Reaction = { persona: string; trigger: Trigger; text: string; state: SpriteState };

type Ctx = { reaction: Reaction | null; react: (r: Reaction) => void };

const ReactionContext = createContext<Ctx | null>(null);
const HOLD_MS = 12_000;

export function spriteStateFor(trigger: Trigger): SpriteState {
  if (trigger.startsWith("completed_") || trigger === "all_done" || trigger === "half_by_noon")
    return "happy";
  if (
    ["skipped", "forgotten", "abandoned", "nothing_by_15", "over_capacity"].includes(trigger) ||
    trigger.startsWith("overdue_")
  )
    return "concerned";
  return "talk";
}

export function ReactionProvider({ children }: { children: React.ReactNode }) {
  const [reaction, setReaction] = useState<Reaction | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const react = useCallback((r: Reaction) => {
    clearTimeout(timer.current);
    setReaction(r);
    timer.current = setTimeout(() => setReaction(null), HOLD_MS);
  }, []);
  useEffect(() => () => clearTimeout(timer.current), []);
  return (
    <ReactionContext.Provider value={{ reaction, react }}>{children}</ReactionContext.Provider>
  );
}

export function useReaction(): Ctx {
  const ctx = useContext(ReactionContext);
  if (!ctx) throw new Error("useReaction outside ReactionProvider");
  return ctx;
}
