"use client";

import { useState } from "react";
import type { QuestProposal } from "@questboard/schema";
import { useLog } from "@/data/log";
import { useReaction } from "@/data/reaction";
import { BOARD_CADENCE, type Board } from "@/lib/board";
import { cadenceOf, describe, planAcceptance, proposalPersona } from "@/game/proposals";
import { packFor } from "@/game/personas";
import { Portrait } from "@/ui/Sprite";

/** Model proposals waiting for the user. Nothing changes until Accept (invariant 3). */
export function ProposalStrip({ board }: { board: Board }) {
  const { store, quests, proposals, config, reload } = useLog();
  const { react } = useReaction();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mine = proposals.filter((p) => {
    const cadence = cadenceOf(p, quests);
    return cadence === null || cadence === BOARD_CADENCE[board];
  });
  if (mine.length === 0) return null;

  async function decide(p: QuestProposal, accept: boolean) {
    setBusy(p.id);
    setError(null);
    try {
      if (!accept) {
        await store.decideProposal(p.id, "rejected");
        await store.recordFeedback({
          quest_id: p.quest_id ?? null,
          action: "rejected",
          diff_op: p.payload,
        });
      } else {
        const d = planAcceptance(p, quests, config, new Date());
        let questId: string | null = p.quest_id ?? null;
        if (d.kind === "stale") {
          await store.decideProposal(p.id, "superseded");
          setError(`Skipped: ${d.reason}.`);
          return;
        }
        if (d.kind === "insert") {
          const q = await store.insertQuest(d.quest);
          questId = q.id;
          await store.insertLines(q.id, q.persona, p.lines ?? []);
        } else if (d.kind === "update") {
          await store.updateQuest(d.questId, d.patch);
        } else {
          await store.updateQuest(d.questId, { status: "abandoned", snoozed_until: null });
        }
        await store.decideProposal(p.id, "accepted");
        await store.recordFeedback({ quest_id: questId, action: "accepted", diff_op: p.payload });
        const persona = proposalPersona(p, quests);
        if (persona && d.kind === "insert") {
          const line = p.lines?.find((l) => l.trigger === "assigned");
          if (line) react({ persona, trigger: "assigned", text: line.text, state: "talk" });
        }
      }
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="panel proposals" aria-label="Suggestions">
      <h2>Suggestions</h2>
      <ul className="proposal-list">
        {mine.map((p) => {
          const slug = proposalPersona(p, quests);
          const pack = slug ? packFor(slug) : undefined;
          return (
            <li
              key={p.id}
              className="proposal"
              style={{ "--accent": pack?.accent ?? "var(--border)" } as React.CSSProperties}
            >
              <Portrait src={pack?.assets.portrait} label={pack?.name ?? "Persona"} />
              <div className="proposal-text">
                <strong>{describe(p, quests)}</strong>
                <span className="muted">
                  {pack?.name ?? "Runner"}: {p.payload.reason}
                </span>
              </div>
              <div className="proposal-actions">
                <button type="button" disabled={busy !== null} onClick={() => decide(p, true)}>
                  Accept
                </button>
                <button type="button" disabled={busy !== null} onClick={() => decide(p, false)}>
                  Reject
                </button>
              </div>
            </li>
          );
        })}
      </ul>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
