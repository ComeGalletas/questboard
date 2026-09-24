import type { Summary } from "@/game/summary";
import { Bar } from "@/ui/Bar";

export function StatsStrip({ summary, showCapacity }: { summary: Summary; showCapacity: boolean }) {
  const { level, streak, stats, capacity } = summary;
  return (
    <section className="panel stats" aria-label="Progress">
      <Bar
        label={`LV ${level.level}`}
        value={level.into}
        max={level.span}
        detail={`${level.into} / ${level.span} XP`}
        color="var(--mom)"
      />
      {showCapacity && (
        <Bar
          label="Capacity"
          value={capacity.plannedMin}
          max={capacity.availableMin}
          over={capacity.over}
          detail={`${capacity.plannedMin} / ${capacity.availableMin} min`}
          color="var(--teacher)"
        />
      )}
      <dl className="stat-row">
        <div data-warn={streak.atRisk || undefined}>
          <dt className="pixel">Streak</dt>
          <dd>
            {streak.days} d{streak.atRisk && " · at risk"}
          </dd>
        </div>
        <div>
          <dt className="pixel">DIS</dt>
          <dd>{stats.discipline}</dd>
        </div>
        <div>
          <dt className="pixel">HLT</dt>
          <dd>{stats.health}</dd>
        </div>
        <div>
          <dt className="pixel">CAR</dt>
          <dd>{stats.career}</dd>
        </div>
      </dl>
    </section>
  );
}
