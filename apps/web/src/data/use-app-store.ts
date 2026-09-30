"use client";

import { useMemo, useSyncExternalStore } from "react";
import { DemoStore } from "@/data/demo-store";
import { demoEnabled, subscribeDemo } from "@/data/demo-flag";
import type { Store } from "@/data/store";
import { SupabaseStore } from "@/data/supabase-store";
import { useSession } from "@/lib/hooks";
import { supabase } from "@/lib/supabase";

/**
 * The store for the current visitor: the demo, the signed-in Supabase user, or null while
 * signed out / still loading. Shared by the board and the desktop companion window.
 */
export function useAppStore() {
  const session = useSession();
  const demo = useSyncExternalStore<boolean | null>(subscribeDemo, demoEnabled, () => null);
  const store: Store | null = useMemo(() => {
    if (demo) return new DemoStore();
    if (session && supabase) return new SupabaseStore(supabase);
    return null;
  }, [demo, session]);
  return { store, session, demo };
}
