"use client";

import { useState } from "react";
import type { Row } from "@/game/summary";
import type { QuestAction } from "@/game/actions";
import { addDays, isoDate } from "@/game/dates";
import { packFor } from "@/game/personas";
import { Portrait } from "@/ui/Sprite";

type Panel = null | "menu" | "complete" | "partial" | "defer";

const STATUS_LABEL: Partial<Record<string, string>> = {
  done: "Done",
  partial: "Partial",
  skipped: "Skipped",
  in_progress: "In progress",
  forgotten: "Forgotten",
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
  const pack = packFor(q.persona);
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
        onClick={() => !row.closed && setPanel(panel ? null : "menu")}
        aria-expanded={panel !== null}
        disabled={row.closed}
      >
        <Portrait src={pack?.assets.portrait} label={pack?.name ?? q.persona} />
        <span className="quest-title">
          {q.title}
          <span className="quest-meta muted">
            {q.estimate_min} min · {q.xp} XP
            {q.priority === 1 && " · P1"}
            {row.carriedFrom && ` · from ${row.carriedFrom}`}
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
        </div>
      )}

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
