"use client";

import { useEffect, useState } from "react";
import type { NotifyTestResult } from "@questboard/schema";
import { useLog } from "@/data/log";
import type { LiveRequest } from "@/data/store";
import { KIND_LABELS, KINDS, notifyTestState, type NotificationKind } from "@/lib/notify-test";
import { runnerStatus } from "@/lib/runner-status";

const POLL_MS = 2000;

/** "Send test notification": asks the PC runner (live queue) to push a test of the chosen kind
 * to every subscribed device right away. The app never holds the VAPID private key and never
 * blocks on the runner; the status line follows the request. Hidden in demo mode. */
export function NotifyTest() {
  const { store, runner } = useLog();
  const [kind, setKind] = useState<NotificationKind>("day_ready");
  const [id, setId] = useState<string | null>(null);
  const [req, setReq] = useState<LiveRequest<NotifyTestResult> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const open =
    id !== null && (req === null || req.status === "pending" || req.status === "running");

  useEffect(() => {
    if (!open || id === null) return;
    let alive = true;
    const timer = setInterval(async () => {
      try {
        const next = await store.getLiveRequest<"notify_test">(id);
        if (alive && next) setReq(next);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    }, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [open, id, store]);

  if (store.kind === "demo") return null;

  async function send() {
    setError(null);
    setReq(null);
    try {
      setId(await store.createLiveRequest("notify_test", { kind }));
    } catch (e) {
      setId(null);
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const offline = runnerStatus(runner?.heartbeat_at, new Date()).kind === "offline";
  const state = id === null ? null : notifyTestState(req, offline);

  return (
    <div className="notify-test">
      <select
        aria-label="Notification kind to test"
        value={kind}
        onChange={(e) => setKind(e.target.value as NotificationKind)}
      >
        {KINDS.map((k) => (
          <option key={k} value={k}>
            {KIND_LABELS[k]}
          </option>
        ))}
      </select>
      <button type="button" className="link" disabled={open} onClick={send}>
        Send test notification
      </button>
      {(state || error) && (
        <div
          className={`notify-test-status ${error || state?.kind === "error" ? "error" : "muted"}`}
          role="status"
        >
          {error ?? state?.text}
          {!error && state && state.devices.length > 0 && (
            <ul>
              {state.devices.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
