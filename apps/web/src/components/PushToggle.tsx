"use client";

import { useState, useSyncExternalStore } from "react";
import { useLog } from "@/data/log";
import { enablePush, pushSupport } from "@/lib/push";

const noop = () => () => {};

/** "Enable notifications on this device". Hidden in demo mode or when push isn't possible. */
export function PushToggle() {
  const { store } = useLog();
  const support = useSyncExternalStore(noop, pushSupport, () => "unsupported" as const);
  const [state, setState] = useState<"idle" | "busy" | "enabled" | "denied" | "error">("idle");

  if (store.kind === "demo" || support !== "ok") return null;
  if (state === "enabled") return <span className="muted">Notifications on for this device</span>;

  return (
    <button
      type="button"
      className="link"
      disabled={state === "busy"}
      onClick={async () => {
        setState("busy");
        try {
          setState(await enablePush(store));
        } catch {
          setState("error");
        }
      }}
    >
      {state === "denied"
        ? "Notifications blocked in browser settings"
        : state === "error"
          ? "Couldn't enable notifications; try again"
          : "Enable notifications on this device"}
    </button>
  );
}
