import type { SpriteState } from "@/data/reaction";

const FRAMES: SpriteState[] = ["idle", "talk", "happy", "concerned", "sleep"];
const SIZE = 32;

/** One 32x32 frame of a persona sheet at an integer scale. A missing state falls back to idle. */
export function Sprite({
  sheet,
  state = "idle",
  scale = 3,
  label,
}: {
  sheet?: string;
  state?: SpriteState;
  scale?: number;
  label: string;
}) {
  const px = SIZE * Math.max(1, Math.round(scale));
  const frame = Math.max(0, FRAMES.indexOf(state));
  return (
    <div
      role="img"
      aria-label={label}
      className="sprite"
      style={{
        width: px,
        height: px,
        backgroundImage: sheet ? `url(${sheet})` : undefined,
        backgroundSize: `${px * FRAMES.length}px ${px}px`,
        backgroundPosition: `-${frame * px}px 0`,
      }}
    />
  );
}

export function Portrait({ src, label }: { src?: string; label: string }) {
  if (!src) return null;
  // eslint-disable-next-line @next/next/no-img-element -- static export, pixel art at 2x
  return <img className="sprite portrait" src={src} alt={label} width={32} height={32} />;
}
