"use client";

import { useState } from "react";
import type { Quest } from "@questboard/schema";
import { useLog } from "@/data/log";
import { BOARD_CADENCE, boardRange, type Board } from "@/lib/board";
import { endOfLocalDay } from "@/game/dates";
import { PACKS, personaForCategory } from "@/game/personas";
import { baseXp } from "@/game/xp";
import { calibration, estimateHint } from "@/game/calibration";

const CATEGORIES: Quest["category"][] = [
  "general",
  "health",
  "learning",
  "jobs",
  "personal",
  "utilities",
  "government",
  "subscription",
  "delivery",
  "travel",
];

/** Manual quest creation. Bill-like categories are allowed here: the user typed it. */
export function QuestForm({ board, onDone }: { board: Board; onDone: () => void }) {
  const { store, config, quests, reload } = useLog();
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<Quest["category"]>("general");
  const [persona, setPersona] = useState<string | null>(null);
  const [estimate, setEstimate] = useState("30");
  const [priority, setPriority] = useState(2);
  const [deadline, setDeadline] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chosenPersona = persona ?? personaForCategory(category, config.persona_order);
  const hint = estimateHint(calibration(quests, new Date()), category, Number(estimate));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const estimate_min = Math.round(Number(estimate));
    if (!(estimate_min >= 1 && estimate_min <= 1440)) {
      setError("Estimate must be 1–1440 minutes");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await store.insertQuest({
        title: title.trim(),
        category,
        persona: chosenPersona,
        cadence: BOARD_CADENCE[board],
        estimate_min,
        priority,
        xp: baseXp({ estimate_min, priority, category }, config.xp_weights),
        scheduled_for: boardRange(board, new Date()).from,
        deadline: deadline ? endOfLocalDay(deadline).toISOString() : null,
        source: "manual",
      });
      await reload();
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="quest-form" onSubmit={submit}>
      <input
        aria-label="Quest title"
        placeholder="New quest"
        value={title}
        maxLength={120}
        onChange={(e) => setTitle(e.target.value)}
        autoFocus
        required
      />
      <div className="quest-form-grid">
        <label>
          Category
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as Quest["category"])}
          >
            {CATEGORIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Persona
          <select value={chosenPersona} onChange={(e) => setPersona(e.target.value)}>
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
            value={estimate}
            onChange={(e) => setEstimate(e.target.value)}
            required
          />
        </label>
        <label>
          Priority
          <select value={priority} onChange={(e) => setPriority(Number(e.target.value))}>
            <option value={1}>P1 high</option>
            <option value={2}>P2 normal</option>
            <option value={3}>P3 low</option>
          </select>
        </label>
        <label>
          Deadline
          <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
        </label>
      </div>
      {hint && <p className="muted hint">{hint}</p>}
      <div className="quest-form-actions">
        <button type="submit" disabled={busy || !title.trim()}>
          Add quest
        </button>
        <button type="button" onClick={onDone}>
          Cancel
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </form>
  );
}
