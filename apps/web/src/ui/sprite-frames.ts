import type { SpriteState } from "@/data/reaction";

export const STATES: SpriteState[] = ["idle", "talk", "happy", "concerned", "sleep"];

/** Column of `state` in a sheet with `frames` frames; a missing frame falls back to idle (0). */
export function frameIndex(state: SpriteState, frames: number = STATES.length): number {
  const i = STATES.indexOf(state);
  return i >= 0 && i < frames ? i : 0;
}
