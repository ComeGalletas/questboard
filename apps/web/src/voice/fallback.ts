// Voice fallback (P1): an utterance the on-device grammar didn't understand goes to the PC
// runner, which answers with a VoiceCommand for the normal confirmation card (invariant 8).
// Pure code. The transcript is short-lived: the app deletes the request row once it has the
// answer (or gives up), and the runner blanks and sweeps old rows (runner/runner/live.py).

import type { VoiceCommand, VoiceFallbackRequest } from "@questboard/schema";
import type { LiveRequest } from "../data/store.ts";
import type { Lang } from "./grammar.ts";

/** The runner deletes voice rows older than this (VOICE_TTL in live.py); the app stops too. */
export const VOICE_TTL_MS = 10 * 60 * 1000;
export const POLL_MS = 1500;
const MAX_UTTERANCE = 300;

export function fallbackRequest(
  utterance: string,
  lang: Lang,
  today: string,
): VoiceFallbackRequest {
  return { utterance: utterance.trim().slice(0, MAX_UTTERANCE), lang, today };
}

export type FallbackOutcome =
  | { kind: "waiting"; text: string }
  | { kind: "command"; command: VoiceCommand }
  | { kind: "failed"; text: string };

/**
 * Where a voice_fallback request stands. `req` null = the row is gone (swept by the runner);
 * `sinceMs`/`nowMs` bound the wait so a transcript never lingers.
 */
export function fallbackOutcome(
  req: LiveRequest<VoiceCommand> | null,
  sinceMs: number,
  nowMs: number,
  offline: boolean,
): FallbackOutcome {
  if (req?.status === "done" && req.result) return { kind: "command", command: req.result };
  if (req === null || nowMs - sinceMs > VOICE_TTL_MS)
    return { kind: "failed", text: "Your PC's runner didn't answer in time." };
  if (req.status === "failed" || req.status === "cancelled")
    return { kind: "failed", text: "Your PC's runner couldn't interpret that." };
  return {
    kind: "waiting",
    text: offline
      ? "Waiting for your PC's runner… (it answers when the PC is on)"
      : "Asking your PC's runner to interpret it…",
  };
}
