import type { SpriteState } from "@/data/reaction";
import { STATES, frameIndex } from "./sprite-frames";

const SIZE = 32;

/** One 32x32 frame of a persona sheet at an integer scale. A missing state falls back to idle. */
export function Sprite({
  sheet,
  frames = STATES.length,
  state = "idle",
  scale = 3,
  label,
}: {
  sheet?: string;
  frames?: number;
  state?: SpriteState;
  scale?: number;
  label: string;
}) {
  const px = SIZE * Math.max(1, Math.round(scale));
  const frame = frameIndex(state, frames);
  return (
    <div
      role="img"
      aria-label={label}
      className="sprite"
      style={{
        width: px,
        height: px,
        backgroundImage: sheet ? `url(${sheet})` : undefined,
        backgroundSize: `${px * frames}px ${px}px`,
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
