"use client";

import { useEffect, useState } from "react";

const CHAR_MS = 28;

function reducedMotion(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

type Props = { speaker: string; text: string; accent: string };

/** Typewriter dialogue. Click or tap to show the whole line at once. */
export function DialogueBox(props: Props) {
  // A new line remounts the box, restarting the typewriter.
  return <Typewriter key={props.text} {...props} />;
}

function Typewriter({ speaker, text, accent }: Props) {
  const [shown, setShown] = useState(() => (reducedMotion() ? text.length : 0));

  useEffect(() => {
    const id = setInterval(() => {
      setShown((n) => {
        if (n >= text.length) clearInterval(id);
        return Math.min(text.length, n + 1);
      });
    }, CHAR_MS);
    return () => clearInterval(id);
  }, [text]);

  return (
    <button
      type="button"
      className="dialogue"
      style={{ "--accent": accent } as React.CSSProperties}
      onClick={() => setShown(text.length)}
    >
      <span className="dialogue-name pixel">{speaker}</span>
      <span className="sr-only">{text}</span>
      <span className="dialogue-text" aria-hidden>
        {text.slice(0, shown)}
        <span className="dialogue-rest">{text.slice(shown)}</span>
      </span>
    </button>
  );
}
