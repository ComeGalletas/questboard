"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { Quest } from "@questboard/schema";
import type { QuestAction } from "@/game/actions";
import { isoDate } from "@/game/dates";
import { PACKS } from "@/game/personas";
import { useLog } from "@/data/log";
import { runnerStatus } from "@/lib/runner-status";
import { POLL_MS, fallbackOutcome, fallbackRequest } from "@/voice/fallback";
import { parseCommand, type Lang } from "@/voice/grammar";
import { setVoiceLang, subscribeVoiceLang, voiceLang } from "@/voice/lang-pref";
import {
  actionFrom,
  draftFor,
  draftProblem,
  newQuestFrom,
  type CreateDraft,
  type Draft,
  type QuestDraft,
} from "@/voice/plan";
import { listen, speechSupported, type Recognizer } from "@/voice/speech";

const EXAMPLES: Record<Lang, string> = {
  en: "add task visit grandma Saturday at 10 · complete laundry · snooze gym for 20 minutes · defer taxes to Monday · what's next",
  es: "crear tarea visitar a la abuela el sábado a las 10 · completar lavar la ropa · posponer gimnasio 20 minutos · aplazar impuestos al lunes · qué sigue",
};

/**
 * Voice (or typed) commands for the board. The grammar runs on the device (P2); what it can't
 * parse goes to the PC runner (P1 voice fallback), which answers with a command for the same
 * card. Every write waits for the confirmation card: a tap on Confirm or a spoken "confirm"
 * (invariant 8).
 */
export function VoiceBar({
  act,
  next,
}: {
  act: (quest: Quest, action: QuestAction) => Promise<boolean>;
  next: Quest | null;
}) {
  const { store, quests, config, reload, runner } = useLog();
  const lang = useSyncExternalStore(subscribeVoiceLang, voiceLang, () => "en" as Lang);
  const canSpeak = useSyncExternalStore(subscribeVoiceLang, speechSupported, () => false);
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const recognizer = useRef<Recognizer | null>(null);
  /** A voice_fallback request in flight (id null until the row exists). */
  const [asking, setAsking] = useState<{ id: string | null; since: number } | null>(null);
  const [waitText, setWaitText] = useState("");
  /** The card holds the runner's interpretation, not the grammar's: say so. */
  const [interpreted, setInterpreted] = useState(false);
  const pendingId = useRef<string | null>(null);

  const today = isoDate(new Date());
  const offline = runnerStatus(runner?.heartbeat_at, new Date()).kind === "offline";

  // Poll the runner's answer; the row (the transcript) is deleted as soon as the wait ends.
  useEffect(() => {
    const id = asking?.id;
    if (!asking || !id) return;
    let alive = true;
    const timer = setInterval(async () => {
      try {
        const req = await store.getLiveRequest<"voice_fallback">(id);
        if (!alive) return;
        const outcome = fallbackOutcome(req, asking.since, Date.now(), offline);
        if (outcome.kind === "waiting") {
          setWaitText(outcome.text);
          return;
        }
        alive = false;
        clearInterval(timer);
        await forget(id);
        setAsking(null);
        if (outcome.kind === "command") {
          const d = draftFor(outcome.command, quests, config, today);
          setInterpreted(d.kind !== "unknown");
          setDraft(d);
        } else {
          setDraft({ kind: "unknown" });
          setNotice(outcome.text);
        }
      } catch (e) {
        if (alive) setNotice(e instanceof Error ? e.message : String(e));
      }
    }, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [asking, store, offline, quests, config, today]); // eslint-disable-line react-hooks/exhaustive-deps -- forget is stable

  // Leaving the board while waiting still deletes the transcript.
  useEffect(
    () => () => {
      if (pendingId.current) void store.deleteLiveRequest(pendingId.current).catch(() => {});
    },
    [store],
  );

  async function forget(id: string) {
    pendingId.current = null;
    await store.deleteLiveRequest(id).catch(() => {});
  }

  async function askRunner(utterance: string) {
    setDraft(null);
    setInterpreted(false);
    setAsking({ id: null, since: Date.now() });
    setWaitText(
      offline
        ? "Waiting for your PC's runner… (it answers when the PC is on)"
        : "Asking your PC's runner to interpret it…",
    );
    try {
      const id = await store.createLiveRequest(
        "voice_fallback",
        fallbackRequest(utterance, lang, today),
      );
      pendingId.current = id;
      setAsking((a) => (a ? { ...a, id } : a));
    } catch (e) {
      setAsking(null);
      setDraft({ kind: "unknown" });
      setNotice(e instanceof Error ? e.message : String(e));
    }
  }

  function cancelAsking() {
    if (asking?.id) void forget(asking.id);
    setAsking(null);
    setNotice("Cancelled.");
  }

  async function confirm(d: Draft | null = draft) {
    if (!d || (d.kind !== "create" && !("candidates" in d))) return;
    const problem = draftProblem(d as CreateDraft | QuestDraft, today);
    if (problem) {
      setNotice(problem);
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      if (d.kind === "create") {
        const q = newQuestFrom(d, config);
        await store.insertQuest(q);
        await reload();
        setNotice(
          `Added “${q.title}”${q.scheduled_for === today ? "" : ` for ${q.scheduled_for}`}.`,
        );
        setDraft(null);
        setInterpreted(false);
        setText("");
      } else {
        const qd = d as QuestDraft;
        const quest = qd.candidates.find((q) => q.id === qd.questId);
        if (quest && (await act(quest, actionFrom(qd)))) {
          setDraft(null);
          setInterpreted(false);
          setText("");
        }
      }
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function handle(utterance: string) {
    const cmd = parseCommand(utterance, today, lang);
    if (cmd.intent === "confirm" || cmd.intent === "cancel") {
      if (!draft) {
        setNotice("Nothing to confirm.");
      } else if (cmd.intent === "confirm") {
        void confirm();
      } else {
        setDraft(null);
        setNotice("Cancelled.");
      }
      return;
    }
    setNotice(null);
    setInterpreted(false);
    const d = draftFor(cmd, quests, config, today);
    // What the grammar can't parse goes to the PC runner (not in the demo: there's no runner).
    if (d.kind === "unknown" && store.kind === "supabase" && utterance.trim()) {
      void askRunner(utterance);
      return;
    }
    setDraft(d);
  }

  function startListening() {
    if (listening || busy) return;
    setNotice(null);
    recognizer.current = listen(
      lang,
      (t) => {
        setText(t);
        handle(t);
      },
      (error) =>
        setNotice(
          error === "not-allowed" ? "Microphone access is blocked." : `Voice error: ${error}`,
        ),
      () => setListening(false),
    );
    setListening(recognizer.current !== null);
  }

  function stopListening() {
    recognizer.current?.stop();
  }

  return (
    <section className="panel voice" aria-label="Voice command">
      <form
        className="voice-bar"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) handle(text);
        }}
      >
        {canSpeak && (
          <button
            type="button"
            className="btn mic"
            aria-pressed={listening}
            onPointerDown={startListening}
            onPointerUp={stopListening}
            onPointerLeave={stopListening}
            onKeyDown={(e) => {
              if (e.key !== " " && e.key !== "Enter") return;
              e.preventDefault();
              if (listening) stopListening();
              else startListening();
            }}
          >
            {listening ? "Listening…" : "Hold to speak"}
          </button>
        )}
        <input
          aria-label="Command"
          placeholder={lang === "es" ? "Di o escribe un comando" : "Say or type a command"}
          value={text}
          maxLength={300}
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit" className="btn" disabled={!text.trim()}>
          Go
        </button>
        <select
          aria-label="Voice language"
          value={lang}
          onChange={(e) => setVoiceLang(e.target.value as Lang)}
        >
          <option value="en">EN</option>
          <option value="es">ES</option>
        </select>
      </form>
      {asking && (
        <div className="voice-card" aria-live="polite">
          <p>{waitText}</p>
          <button type="button" className="btn" onClick={cancelAsking}>
            Cancel
          </button>
        </div>
      )}
      {draft && (
        <VoiceCard
          draft={draft}
          next={next}
          today={today}
          busy={busy}
          lang={lang}
          note={interpreted ? "Interpreted by your PC's runner: check it before confirming." : null}
          onChange={setDraft}
          onConfirm={() => void confirm()}
          onClose={() => {
            setDraft(null);
            setInterpreted(false);
          }}
        />
      )}
      {notice && <p className="muted voice-notice">{notice}</p>}
    </section>
  );
}

function VoiceCard({
  draft,
  next,
  today,
  busy,
  lang,
  note,
  onChange,
  onConfirm,
  onClose,
}: {
  draft: Draft;
  next: Quest | null;
  today: string;
  busy: boolean;
  lang: Lang;
  note: string | null;
  onChange: (d: Draft) => void;
  onConfirm: () => void;
  onClose: () => void;
}) {
  if (draft.kind === "whats_next") {
    return (
      <div className="voice-card">
        <p>
          {next
            ? `Next up: ${next.title} (${next.estimate_min} min)`
            : "Nothing left on today's board."}
        </p>
        <button type="button" className="btn" onClick={onClose}>
          Close
        </button>
      </div>
    );
  }
  if (draft.kind === "unknown") {
    return (
      <div className="voice-card">
        <p>I didn&apos;t catch a command. Try: {EXAMPLES[lang]}</p>
        <button type="button" className="btn" onClick={onClose}>
          Close
        </button>
      </div>
    );
  }

  const problem = draftProblem(draft, today);
  const actions = (
    <>
      {note && <p className="muted">{note}</p>}
      <div className="quest-form-actions">
        <button type="button" onClick={onConfirm} disabled={busy || problem !== null}>
          Confirm
        </button>
        <button type="button" onClick={onClose}>
          Cancel
        </button>
        <span className="muted">
          {problem ?? (lang === "es" ? "o di “confirmar”" : "or say “confirm”")}
        </span>
      </div>
    </>
  );

  if (draft.kind === "create") {
    const set = (patch: Partial<CreateDraft>) => onChange({ ...draft, ...patch });
    return (
      <div className="quest-form voice-card" aria-label="Confirm new quest">
        <input
          aria-label="Quest title"
          value={draft.title}
          maxLength={120}
          onChange={(e) => set({ title: e.target.value })}
        />
        <div className="quest-form-grid">
          <label>
            Day
            <input
              type="date"
              value={draft.date}
              min={today}
              onChange={(e) => set({ date: e.target.value })}
            />
          </label>
          <label>
            Time
            <input type="time" value={draft.time} onChange={(e) => set({ time: e.target.value })} />
          </label>
          <label>
            Persona
            <select value={draft.persona} onChange={(e) => set({ persona: e.target.value })}>
              {PACKS.map((p) => (
                <option key={p.slug} value={p.slug}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Estimate (min)
            <input
              type="number"
              min={1}
              max={1440}
              inputMode="numeric"
              value={draft.estimate}
              onChange={(e) => set({ estimate: Number(e.target.value) })}
            />
          </label>
        </div>
        {actions}
      </div>
    );
  }

  const set = (patch: Partial<QuestDraft>) => onChange({ ...draft, ...patch });
  const verb = { complete: "Complete", snooze: "Snooze", defer: "Defer" }[draft.kind];
  return (
    <div className="quest-form voice-card" aria-label={`Confirm ${draft.kind}`}>
      <div className="quest-form-grid">
        <label>
          {verb}
          <select
            value={draft.questId ?? ""}
            onChange={(e) => set({ questId: e.target.value || null })}
          >
            <option value="">Pick a quest{draft.said ? ` (“${draft.said}”)` : ""}</option>
            {draft.candidates.map((q) => (
              <option key={q.id} value={q.id}>
                {q.title}
              </option>
            ))}
          </select>
        </label>
        {draft.kind === "defer" ? (
          <label>
            To
            <input type="date" value={draft.date} onChange={(e) => set({ date: e.target.value })} />
          </label>
        ) : (
          <label>
            {draft.kind === "complete" ? "Actual (min)" : "For (min)"}
            <input
              type="number"
              min={draft.kind === "complete" ? 0 : 1}
              max={1440}
              inputMode="numeric"
              value={draft.minutes}
              onChange={(e) => set({ minutes: Number(e.target.value) })}
            />
          </label>
        )}
      </div>
      {actions}
    </div>
  );
}
