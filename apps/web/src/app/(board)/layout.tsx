"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useSyncExternalStore } from "react";
import { StatusPill } from "@/components/StatusPill";
import { DemoStore } from "@/data/demo-store";
import { demoEnabled, setDemo, subscribeDemo } from "@/data/demo-flag";
import { LogProvider } from "@/data/log";
import { ReactionProvider } from "@/data/reaction";
import type { Store } from "@/data/store";
import { SupabaseStore } from "@/data/supabase-store";
import { useSession } from "@/lib/hooks";
import { supabase } from "@/lib/supabase";

const TABS = [
  { href: "/today", label: "Today" },
  { href: "/week", label: "Week" },
  { href: "/month", label: "Month" },
];

export default function BoardLayout({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const demo = useSyncExternalStore<boolean | null>(subscribeDemo, demoEnabled, () => null);

  const store: Store | null = useMemo(() => {
    if (demo) return new DemoStore();
    if (session && supabase) return new SupabaseStore(supabase);
    return null;
  }, [demo, session]);

  useEffect(() => {
    if (demo === false && session === null) router.replace("/login");
  }, [demo, session, router]);

  if (!store) return null;

  function signOut() {
    if (store?.kind === "demo") {
      setDemo(false);
      router.replace("/login");
    } else {
      void supabase?.auth.signOut();
    }
  }

  return (
    <LogProvider store={store}>
      <ReactionProvider>
        <div className="shell">
          <header className="topbar">
            <h1>Questboard</h1>
            <nav className="tabs" aria-label="Boards">
              {TABS.map((t) => (
                <Link
                  key={t.href}
                  href={t.href}
                  aria-current={pathname.startsWith(t.href) ? "page" : undefined}
                >
                  {t.label}
                </Link>
              ))}
            </nav>
            <StatusPill />
          </header>
          <main>{children}</main>
          <footer className="footer muted">
            <button type="button" className="link" onClick={signOut}>
              {store.kind === "demo" ? "Leave demo" : "Sign out"}
            </button>
            {store.kind === "demo" && (
              <button
                type="button"
                className="link"
                onClick={() => {
                  DemoStore.reset();
                  window.location.reload();
                }}
              >
                Reset demo data
              </button>
            )}
          </footer>
        </div>
      </ReactionProvider>
    </LogProvider>
  );
}
