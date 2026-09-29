"use client";

import { useEffect, useState } from "react";
import type { ReplanResult } from "@questboard/schema";
import { useLog } from "@/data/log";
import type { LiveRequest } from "@/data/store";
import type { Board } from "@/lib/board";
import { BOARD_JOB } from "@/lib/planner";
import { runnerStatus } from "@/lib/runner-status";
import { suggestState } from "@/lib/suggest";

const POLL_MS = 2000;
const LABEL: Record<Board, string> = {
  today: "Suggest quests",
  week: "Suggest for the week",
  month: "Suggest for the month",
};

/** "Suggest quests now": asks the PC runner (P1 live queue) for a fresh plan for this board.
 * The answer arrives as proposals; nothing changes until the user accepts (invariant 3). */
export function SuggestButton({ board }: { board: Board }) {
  const { store, runner, reload } = useLog();
  const [id, setId] = useState<string | null>(null);
  const [req, setReq] = useState<LiveRequest<ReplanResult> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const open =
    id !== null && (req === null || req.status === "pending" || req.status === "running");

  useEffect(() => {
    if (!open || id === null) return;
    let alive = true;
    const timer = setInterval(async () => {
      try {
        const next = await store.getLiveRequest<"replan">(id);
        if (!alive || !next) return;
        setReq(next);
        if (next.status === "done") await reload();
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    }, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [open, id, store, reload]);

  async function ask() {
    setError(null);
    setReq(null);
    try {
      setId(await store.createLiveRequest("replan", { job: BOARD_JOB[board] }));
    } catch (e) {
      setId(null);
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const offline = runnerStatus(runner?.heartbeat_at, new Date()).kind === "offline";
  const state = id === null ? null : suggestState(req, offline);

  return (
    <>
      <button type="button" className="btn" disabled={open} onClick={ask}>
        {LABEL[board]}
      </button>
      {(state || error) && (
        <p
          className={`suggest-status ${error || state?.kind === "error" ? "error" : "muted"}`}
          role="status"
        >
          {error ?? state?.text}
        </p>
      )}
    </>
  );
}
