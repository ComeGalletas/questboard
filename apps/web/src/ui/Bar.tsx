/** Segmented pixel bar. `over` turns it to the warning colour. */
export function Bar({
  value,
  max,
  label,
  detail,
  color = "var(--ok)",
  over = false,
}: {
  value: number;
  max: number;
  label: string;
  detail?: string;
  color?: string;
  over?: boolean;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="bar">
      <div className="bar-head">
        <span className="pixel">{label}</span>
        {detail && <span className="muted">{detail}</span>}
      </div>
      <div
        className="bar-track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
      >
        <div
          className="bar-fill"
          style={{ width: `${pct}%`, background: over ? "var(--warn)" : color }}
        />
      </div>
    </div>
  );
}
