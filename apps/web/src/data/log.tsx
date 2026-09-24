"use client";

// Loads the quest log, config, cached lines and runner state from the active store and keeps
// them fresh (realtime + polling). Every screen renders from this cache; nothing waits on a model.

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { Config, PersonaLine, Quest, QuestProposal, RunnerState } from "@questboard/schema";
import type { Store } from "./store";
import { DEMO_CONFIG } from "./demo-store";

export type Log = {
  store: Store;
  quests: Quest[];
  config: Config;
  lines: PersonaLine[];
  proposals: QuestProposal[];
  runner: RunnerState | null;
  loaded: boolean;
  error: string | null;
  reload: () => Promise<void>;
};

const LogContext = createContext<Log | null>(null);
const POLL_MS = 60_000;

export function LogProvider({ store, children }: { store: Store; children: React.ReactNode }) {
  const [state, setState] = useState<Omit<Log, "store" | "reload">>({
    quests: [],
    config: DEMO_CONFIG,
    lines: [],
    proposals: [],
    runner: null,
    loaded: false,
    error: null,
  });
  const alive = useRef(true);

  const reload = useCallback(async () => {
    try {
      const [quests, config, lines, proposals, runner] = await Promise.all([
        store.listQuests(),
        store.getConfig(),
        store.listLines(),
        store.listPendingProposals(),
        store.getRunnerState(),
      ]);
      if (!alive.current) return;
      setState({
        quests,
        config: config ?? DEMO_CONFIG,
        lines,
        proposals,
        runner,
        loaded: true,
        error: null,
      });
    } catch (e) {
      if (alive.current) {
        setState((s) => ({
          ...s,
          loaded: true,
          error: e instanceof Error ? e.message : String(e),
        }));
      }
    }
  }, [store]);

  useEffect(() => {
    alive.current = true;
    reload();
    const unsubscribe = store.subscribe(() => void reload());
    const timer = setInterval(reload, POLL_MS);
    return () => {
      alive.current = false;
      unsubscribe();
      clearInterval(timer);
    };
  }, [store, reload]);

  return <LogContext.Provider value={{ ...state, store, reload }}>{children}</LogContext.Provider>;
}

export function useLog(): Log {
  const log = useContext(LogContext);
  if (!log) throw new Error("useLog outside LogProvider");
  return log;
}
