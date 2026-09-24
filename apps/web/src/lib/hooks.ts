"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import type { Quest, RunnerState } from "@questboard/schema";
import { supabase } from "./supabase";
import { BOARD_CADENCE, boardRange, type Board } from "./board";

/** undefined = still reading the stored session; null = signed out. */
export function useSession(): Session | null | undefined {
  const [session, setSession] = useState<Session | null | undefined>(supabase ? undefined : null);
  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);
  return session;
}

/** Re-renders every `ms` so relative times stay fresh. */
export function useNow(ms = 30_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

const POLL_MS = 60_000;

/** runner_state via realtime, with polling as a fallback when the socket drops. */
export function useRunnerState(): RunnerState | null {
  const [state, setState] = useState<RunnerState | null>(null);
  useEffect(() => {
    const client = supabase;
    if (!client) return;
    let alive = true;
    const load = async () => {
      const { data } = await client.from("runner_state").select("*").maybeSingle();
      if (alive) setState((data as RunnerState | null) ?? null);
    };
    load();
    const timer = setInterval(load, POLL_MS);
    const channel = client
      .channel("runner_state")
      .on("postgres_changes", { event: "*", schema: "public", table: "runner_state" }, (p) => {
        if (p.new && "user_id" in p.new) setState(p.new as RunnerState);
      })
      .subscribe();
    return () => {
      alive = false;
      clearInterval(timer);
      client.removeChannel(channel);
    };
  }, []);
  return state;
}

export type QuestsResult = { quests: Quest[]; loaded: boolean; error: string | null };

/** Quests for a board, straight from the cache; refreshed on any realtime change. */
export function useBoardQuests(board: Board): QuestsResult {
  const [result, setResult] = useState<QuestsResult>({ quests: [], loaded: false, error: null });
  useEffect(() => {
    const client = supabase;
    if (!client) return;
    let alive = true;
    const { from, to } = boardRange(board, new Date());
    const load = async () => {
      const { data, error } = await client
        .from("quests")
        .select("*")
        .eq("cadence", BOARD_CADENCE[board])
        .gte("scheduled_for", from)
        .lte("scheduled_for", to)
        .order("priority")
        .order("created_at");
      if (!alive) return;
      setResult({
        quests: (data as Quest[] | null) ?? [],
        loaded: true,
        error: error?.message ?? null,
      });
    };
    load();
    const channel = client
      .channel(`quests:${board}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "quests" }, load)
      .subscribe();
    return () => {
      alive = false;
      client.removeChannel(channel);
    };
  }, [board]);
  return result;
}
