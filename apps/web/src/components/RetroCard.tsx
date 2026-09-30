"use client";

// The weekly / monthly retro card (Week / Month board). The lead persona asks the questions the
// runner wrote about the period that ended; answers are saved and shape later plans (the runner
// passes them to the planning prompts as the user's own reflection). Skipping is always fine.

import { useEffect, useState } from "react";
import type { Retro } from "@questboard/schema";
import { useLog } from "@/data/log";
import { isoDate } from "@/game/dates";
import { packFor } from "@/game/personas";
import { MAX_ANSWER, periodLabel, retroPatch, retroToShow } from "@/game/retro";
import { Portrait } from "@/ui/Sprite";

export function RetroCard({ cadence, speaker }: { cadence: Retro["cadence"]; speaker: string }) {
  const { store } = useLog();
  const [retro, setRetro] = useState<Retro | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    store
      .listRetros(cadence)
      .then((rows) => alive && setRetro(retroToShow(rows, isoDate(new Date()))))
      .catch(() => {}); // no retro card offline; nothing else depends on it
    return () => {
      alive = false;
    };
  }, [store, cadence]);

  if (done) return <p className="panel retro-done muted">{done}</p>;
  if (!retro) return null;

  const pack = packFor(speaker);
  const current = retro;

  async function save(skip: boolean) {
    setBusy(true);
    setError(null);
    try {
      const patch = retroPatch(current, skip ? {} : form, new Date());
      await store.saveRetro(current.id, patch);
      setDone(
        patch.status === "answered"
          ? `Saved. Your next plans will take it into account; press “Suggest for the ${cadence === "weekly" ? "week" : "month"}” for a fresh one now.`
          : "Skipped. See you next time.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="panel retro"
      aria-label={`${cadence === "weekly" ? "Weekly" : "Monthly"} retro`}
      style={{ "--accent": pack?.accent ?? "var(--border)" } as React.CSSProperties}
    >
      <div className="retro-head">
        <Portrait src={pack?.assets.portrait} label={pack?.name ?? speaker} />
        <h3 className="pixel">Retro · {periodLabel(retro)}</h3>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void save(false);
        }}
      >
        {retro.questions.map((q) => (
          <label key={q.id} className="retro-q">
            {q.text}
            <textarea
              rows={2}
              maxLength={MAX_ANSWER}
              value={form[q.id] ?? ""}
              onChange={(e) => setForm({ ...form, [q.id]: e.target.value })}
            />
          </label>
        ))}
        <div className="quest-form-actions">
          <button type="submit" className="btn" disabled={busy}>
            Save
          </button>
          <button type="button" className="btn" disabled={busy} onClick={() => void save(true)}>
            Skip
          </button>
          <span className="muted">Only you and your planner see this.</span>
        </div>
        {error && <p className="error">{error}</p>}
      </form>
    </section>
  );
}
