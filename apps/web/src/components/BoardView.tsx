"use client";

import type { Board } from "@/lib/board";
import { useBoardQuests } from "@/lib/hooks";

const TITLES: Record<Board, string> = { today: "Today", week: "This week", month: "This month" };

export function BoardView({ board }: { board: Board }) {
  const { quests, loaded, error } = useBoardQuests(board);
  return (
    <section className="panel board" aria-labelledby={`${board}-title`}>
      <h2 id={`${board}-title`}>{TITLES[board]}</h2>
      {error && <p className="error">Could not load quests: {error}</p>}
      {loaded && quests.length === 0 && !error && (
        <p className="empty">
          No quests yet. The board fills in after the runner&apos;s next pass.
        </p>
      )}
      {quests.length > 0 && (
        <ul className="quest-list">
          {quests.map((q) => (
            <li key={q.id} style={{ "--accent": `var(--${q.persona})` } as React.CSSProperties}>
              <span>{q.title}</span>
              <span className="muted">{q.estimate_min} min</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
