"use client";

import { useState } from "react";
import type { Quest } from "@questboard/schema";
import { useLog } from "@/data/log";
import type { Row } from "@/game/summary";
import type { QuestAction } from "@/game/actions";
import { addDays, isoDate } from "@/game/dates";
import {
  CATEGORIES,
  deletionFor,
  deletionMessage,
  editFormFor,
  editPatch,
  type EditForm,
} from "@/game/edit";
import { PACKS, packFor } from "@/game/personas";
import { Portrait } from "@/ui/Sprite";

type Panel = null | "menu" | "complete" | "partial" | "defer" | "edit" | "delete";

const STATUS_LABEL: Partial<Record<string, string>> = {
  done: "Done",
  partial: "Partial",
  skipped: "Skipped",
  in_progress: "In progress",
  abandoned: "Abandoned",
};

export function QuestRow({
  row,
  onAction,
}: {
  row: Row;
  onAction: (a: QuestAction) => Promise<boolean>;
}) {
  const q = row.quest;
  const { store, quests, config, reload } = useLog();
  const pack = packFor(q.persona);
  const [form, setForm] = useState<EditForm>(() => editFormFor(q));
  const [error, setError] = useState<string | null>(null);
  const [panel, setPanel] = useState<Panel>(null);
  const [minutes, setMinutes] = useState(String(q.estimate_min));
  const [deferTo, setDeferTo] = useState(() => addDays(isoDate(new Date()), 1));
  const [busy, setBusy] = useState(false);

  async function run(action: QuestAction) {
    setBusy(true);
    const ok = await onAction(action);
    setBusy(false);
    if (ok) setPanel(null);
  }

  // Edits and deletes are the user's own corrections: straight to the store, no reaction.
  async function change(work: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await work();
      await reload();
      setPanel(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function saveEdit() {
    const r = editPatch(q, form, config.xp_weights);
    if (!r.ok) {
      setError(r.reason);
      return;
    }
    if (!Object.keys(r.patch).length) {
      setPanel(null);
      return;
    }
    void change(() => store.updateQuest(q.id, r.patch));
  }

  const deletion = panel === "delete" ? deletionFor(q, quests) : null;

  const progress = row.progress;
  const badge = row.snoozed
    ? `Snoozed until ${new Date(q.snoozed_until!).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
    : !row.closed && progress?.ready
      ? "Ready to turn in"
      : STATUS_LABEL[q.status];

  // A parent's time spent is what its steps logged; start the form there.
  function openFinish(kind: "complete" | "partial") {
    setMinutes(String(progress && progress.doneMin > 0 ? progress.doneMin : q.estimate_min));
    setPanel(kind);
  }

  return (
    <li
      className="quest"
      data-closed={row.closed || undefined}
      data-snoozed={row.snoozed || undefined}
      style={{ "--accent": pack?.accent ?? "var(--border)" } as React.CSSProperties}
    >
      <button
        type="button"
        className="quest-main"
        onClick={() => {
          setError(null);
          setPanel(panel ? null : "menu");
        }}
        aria-expanded={panel !== null}
      >
        <Portrait src={pack?.assets.portrait} label={pack?.name ?? q.persona} />
        <span className="quest-title">
          {q.title}
          <span className="quest-meta muted">
            {q.estimate_min} min · {q.xp} XP
            {q.priority === 1 && " · P1"}
            {row.carriedFrom && ` · from ${row.carriedFrom}`}
            {!!q.forgotten_on?.length && ` · forgotten ${q.forgotten_on.length}×`}
            {q.deadline && ` · due ${new Date(q.deadline).toLocaleDateString()}`}
            {row.parent && ` · step of ${row.parent.title}`}
          </span>
          {progress && (
            <span className="quest-progress muted">
              <span
                className="bar-track"
                role="meter"
                aria-label="Progress from steps"
                aria-valuemin={0}
                aria-valuemax={progress.targetMin}
                aria-valuenow={Math.min(progress.doneMin, progress.targetMin)}
              >
                <span
                  className="bar-fill"
                  style={{
                    width: `${Math.min(100, (progress.doneMin / Math.max(1, progress.targetMin)) * 100)}%`,
                    background: "var(--accent)",
                  }}
                />
              </span>
              {progress.done}/{progress.total} steps · {progress.doneMin}/{progress.targetMin} min
            </span>
          )}
        </span>
        {badge && <span className="quest-badge pixel">{badge}</span>}
        {row.closed && q.xp_awarded != null && (
          <span className="quest-badge pixel">+{q.xp_awarded}</span>
        )}
      </button>

      {panel === "menu" && (
        <div className="quest-actions">
          {!row.closed && (
            <>
              {q.status !== "in_progress" && (
                <button type="button" disabled={busy} onClick={() => run({ kind: "start" })}>
                  Start
                </button>
              )}
              <button type="button" disabled={busy} onClick={() => openFinish("complete")}>
                Done
              </button>
              <button type="button" disabled={busy} onClick={() => openFinish("partial")}>
                Partial
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => run({ kind: "snooze", minutes: 30 })}
              >
                Snooze 30m
              </button>
              <button type="button" disabled={busy} onClick={() => setPanel("defer")}>
                Defer
              </button>
              <button type="button" disabled={busy} onClick={() => run({ kind: "skip" })}>
                Skip
              </button>
            </>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setForm(editFormFor(q));
              setPanel("edit");
            }}
          >
            Edit
          </button>
          <button type="button" disabled={busy} onClick={() => setPanel("delete")}>
            Delete
          </button>
        </div>
      )}

      {panel === "edit" && (
        <form
          className="quest-form quest-edit"
          aria-label={`Edit ${q.title}`}
          onSubmit={(e) => {
            e.preventDefault();
            saveEdit();
          }}
        >
          <input
            aria-label="Quest title"
            value={form.title}
            maxLength={120}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            required
          />
          <div className="quest-form-grid">
            <label>
              Category
              <select
                value={form.category}
                onChange={(e) =>
                  setForm({ ...form, category: e.target.value as Quest["category"] })
                }
              >
                {CATEGORIES.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>
              Persona
              <select
                value={form.persona}
                onChange={(e) => setForm({ ...form, persona: e.target.value })}
              >
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
                value={form.estimate}
                onChange={(e) => setForm({ ...form, estimate: e.target.value })}
                required
              />
            </label>
            <label>
              Priority
              <select
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
              >
                <option value={1}>P1 high</option>
                <option value={2}>P2 normal</option>
                <option value={3}>P3 low</option>
              </select>
            </label>
            {q.scheduled_for && (
              <label>
                Day
                <input
                  type="date"
                  value={form.day}
                  onChange={(e) => setForm({ ...form, day: e.target.value })}
                  required
                />
              </label>
            )}
            <label>
              Deadline
              <input
                type="date"
                value={form.deadline}
                onChange={(e) => setForm({ ...form, deadline: e.target.value })}
              />
            </label>
          </div>
          <div className="quest-form-actions">
            <button type="submit" disabled={busy || !form.title.trim()}>
              Save
            </button>
            <button type="button" onClick={() => setPanel("menu")}>
              Back
            </button>
          </div>
        </form>
      )}

      {panel === "delete" && deletion && (
        <div className="quest-actions" role="alertdialog" aria-label={`Delete ${q.title}`}>
          <p>{deletionMessage(q, deletion)}</p>
          <button
            type="button"
            className="danger"
            disabled={busy}
            onClick={() => void change(() => store.deleteQuests(deletion.ids))}
          >
            Delete
          </button>
          <button type="button" onClick={() => setPanel("menu")}>
            Back
          </button>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {(panel === "complete" || panel === "partial") && (
        <form
          className="quest-actions"
          onSubmit={(e) => {
            e.preventDefault();
            run({ kind: panel, actualMin: Number(minutes) });
          }}
        >
          <label>
            Time spent (min)
            <input
              type="number"
              min={0}
              inputMode="numeric"
              value={minutes}
              onChange={(e) => setMinutes(e.target.value)}
              autoFocus
              required
            />
          </label>
          <button type="submit" disabled={busy}>
            {panel === "complete" ? "Complete" : "Log partial"}
          </button>
          <button type="button" onClick={() => setPanel("menu")}>
            Back
          </button>
        </form>
      )}

      {panel === "defer" && (
        <form
          className="quest-actions"
          onSubmit={(e) => {
            e.preventDefault();
            run({ kind: "defer", to: deferTo });
          }}
        >
          <label>
            Move to
            <input
              type="date"
              min={addDays(isoDate(new Date()), 1)}
              value={deferTo}
              onChange={(e) => setDeferTo(e.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={busy}>
            Defer
          </button>
          <button type="button" onClick={() => setPanel("menu")}>
            Back
          </button>
        </form>
      )}
    </li>
  );
}
