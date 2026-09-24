// The voice language (recognition + which grammar is tried first). Per device, in localStorage.

import type { Lang } from "./grammar.ts";

const KEY = "questboard.voice.lang";
const listeners = new Set<() => void>();

export function voiceLang(): Lang {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === "en" || stored === "es") return stored;
    return navigator.language.toLowerCase().startsWith("es") ? "es" : "en";
  } catch {
    return "en";
  }
}

/** For useSyncExternalStore. */
export function subscribeVoiceLang(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function setVoiceLang(lang: Lang): void {
  try {
    localStorage.setItem(KEY, lang);
  } catch {
    // storage unavailable: the choice lasts until reload
  }
  for (const fn of listeners) fn();
}
