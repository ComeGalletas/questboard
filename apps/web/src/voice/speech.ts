// Web Speech API (where the browser has it). The transcript stays in memory: it is parsed and
// shown, never logged or stored.

export type Recognizer = {
  start(): void;
  stop(): void;
  abort(): void;
};

type RecognitionEvent = { results: ArrayLike<ArrayLike<{ transcript: string }>> };
type Recognition = Recognizer & {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
};
type RecognitionCtor = new () => Recognition;

function ctor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function speechSupported(): boolean {
  return ctor() !== null;
}

/** One utterance: calls onText with the final transcript, onEnd when listening stops. */
export function listen(
  lang: "en" | "es",
  onText: (text: string) => void,
  onError: (error: string) => void,
  onEnd: () => void,
): Recognizer | null {
  const Ctor = ctor();
  if (!Ctor) return null;
  const r = new Ctor();
  r.lang = lang === "es" ? "es-CO" : "en-US";
  r.interimResults = false;
  r.continuous = false;
  r.maxAlternatives = 1;
  r.onresult = (e) => {
    const text = Array.from(e.results)
      .map((alts) => alts[0]?.transcript ?? "")
      .join(" ")
      .trim();
    if (text) onText(text);
  };
  r.onerror = (e) => onError(e.error);
  r.onend = onEnd;
  r.start();
  return r;
}
