"use client";

import { useMemo, useState } from "react";
import type { Board } from "@/lib/board";
import { useLog } from "@/data/log";
import { finishedCount, summarize } from "@/game/summary";
import { useNow } from "@/lib/hooks";
import { PersonaPanel } from "./PersonaPanel";
import { QuestForm } from "./QuestForm";
import { QuestRow } from "./QuestRow";
import { StatsStrip } from "./StatsStrip";
import { useQuestActions } from "./useQuestActions";

const TITLES: Record<Board, string> = { today: "Today", week: "This week", month: "This month" };

export function BoardView({ board }: { board: Board }) {
  const { quests, config, loaded, error } = useLog();
  const now = useNow(60_000);
  const summary = useMemo(
    () => summarize(quests, config, board, now),
    [quests, config, board, now],
  );
  const { act, error: actionError } = useQuestActions(summary.mood, summary.next);
  const [adding, setAdding] = useState(false);
  const done = finishedCount(summary.rows);

  return (
    <div className="board-layout">
      <PersonaPanel summary={summary} />
      <StatsStrip summary={summary} showCapacity={board === "today"} />
      <section className="panel board" aria-labelledby={`${board}-title`}>
        <div className="board-head">
          <h2 id={`${board}-title`}>
            {TITLES[board]}
            {summary.rows.length > 0 && (
              <span className="muted count">
                {" "}
                {done}/{summary.rows.length}
              </span>
            )}
          </h2>
          {!adding && (
            <button type="button" className="btn" onClick={() => setAdding(true)}>
              + Quest
            </button>
          )}
        </div>
        {adding && <QuestForm board={board} onDone={() => setAdding(false)} />}
        {error && <p className="error">Could not load quests: {error}</p>}
        {actionError && <p className="error">{actionError}</p>}
        {loaded && summary.rows.length === 0 && !error && !adding && (
          <p className="empty">No quests yet. Add one, or wait for the runner&apos;s next pass.</p>
        )}
        {summary.rows.length > 0 && (
          <ul className="quest-list">
            {summary.rows.map((row) => (
              <QuestRow key={row.quest.id} row={row} onAction={(a) => act(row.quest, a)} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
