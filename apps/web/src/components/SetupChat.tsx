"use client";

import { useEffect, useRef, useState } from "react";
import type { ConfigPatch, SetupRequest } from "@questboard/schema";
import { useLog } from "@/data/log";
import { applyPatch, describePatch } from "@/game/configPatch";
import { runnerStatus } from "@/lib/runner-status";

type Message = SetupRequest["messages"][number];

const GREETING =
  "Hi! I'll help you set up your goals, free time and quiet hours. What would you like to work on?";
const POLL_MS = 2000;
const SLOW_MS = 10_000;

/** Setup assistant (P1 via the PC runner). Suggestions are applied only when you tap Apply. */
export function SetupChat() {
  const { store, config, runner, reload } = useLog();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [waiting, setWaiting] = useState<{ id: string; since: number } | null>(null);
  const [slow, setSlow] = useState(false);
  const [patch, setPatch] = useState<ConfigPatch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages, waiting]);

  useEffect(() => {
    if (!waiting) return;
    let alive = true;
    const timer = setInterval(async () => {
      if (Date.now() - waiting.since > SLOW_MS) setSlow(true);
      try {
        const req = await store.getLiveRequest(waiting.id);
        if (!alive || !req) return;
        if (req.status === "done" && req.result) {
          setMessages((m) => [...m, { role: "assistant", content: req.result!.reply }]);
          setPatch(req.result.config_patch ?? null);
          setDone(req.result.done);
          setWaiting(null);
        } else if (req.status === "failed" || req.status === "cancelled") {
          setError(req.error ?? "The runner couldn't answer.");
          setWaiting(null);
        }
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    }, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [waiting, store]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || waiting) return;
    const next: Message[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setDraft("");
    setError(null);
    setSlow(false);
    setPatch(null);
    try {
      // The greeting is UI only; the runner sees the real conversation.
      const id = await store.createLiveRequest("setup_assistant", { messages: next });
      setWaiting({ id, since: Date.now() });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function apply() {
    if (!patch) return;
    try {
      await store.saveConfig(applyPatch(config, patch));
      setPatch(null);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const offline = runnerStatus(runner?.heartbeat_at, new Date()).kind === "offline";
  const changes = patch ? describePatch(config, patch) : [];

  return (
    <section className="panel setup" aria-label="Setup assistant">
      <h2>Setup assistant</h2>
      <ol className="chat">
        <li className="chat-msg" data-role="assistant">
          {GREETING}
        </li>
        {messages.map((m, i) => (
          <li key={i} className="chat-msg" data-role={m.role}>
            {m.content}
          </li>
        ))}
        {waiting && (
          <li className="chat-msg muted" data-role="assistant">
            {slow && offline
              ? "Waiting for your PC's runner… (it answers when the PC is on)"
              : "Thinking…"}
          </li>
        )}
      </ol>
      {changes.length > 0 && (
        <div className="patch-review">
          <h3 className="pixel">Suggested settings</h3>
          <dl>
            {changes.map((c) => (
              <div key={c.key}>
                <dt>{c.key}</dt>
                <dd>
                  <span className="muted">{c.before}</span> → <strong>{c.after}</strong>
                </dd>
              </div>
            ))}
          </dl>
          <div className="quest-form-actions">
            <button type="button" className="btn" onClick={apply}>
              Apply
            </button>
            <button type="button" className="btn" onClick={() => setPatch(null)}>
              Not now
            </button>
          </div>
        </div>
      )}
      {done && <p className="muted">Setup looks complete. You can keep chatting to adjust.</p>}
      {error && <p className="error">{error}</p>}
      <form className="chat-input" onSubmit={send}>
        <input
          aria-label="Message"
          placeholder="Type your answer"
          value={draft}
          maxLength={2000}
          onChange={(e) => setDraft(e.target.value)}
          disabled={!!waiting}
        />
        <button type="submit" className="btn" disabled={!!waiting || !draft.trim()}>
          Send
        </button>
      </form>
      <div ref={bottom} />
    </section>
  );
}
