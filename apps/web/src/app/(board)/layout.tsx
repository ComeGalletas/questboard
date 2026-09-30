"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { MilestoneWatcher } from "@/components/MilestoneWatcher";
import { NotifyTest } from "@/components/NotifyTest";
import { PcNotifier } from "@/components/PcNotifier";
import { PushToggle } from "@/components/PushToggle";
import { StatusPill } from "@/components/StatusPill";
import { DemoStore } from "@/data/demo-store";
import { setDemo } from "@/data/demo-flag";
import { LogProvider } from "@/data/log";
import { ReactionProvider } from "@/data/reaction";
import { useAppStore } from "@/data/use-app-store";
import { targetToPath } from "@/lib/deeplink";
import { onDeepLink } from "@/lib/desktop";
import { supabase } from "@/lib/supabase";

const TABS = [
  { href: "/today", label: "Today" },
  { href: "/week", label: "Week" },
  { href: "/month", label: "Month" },
  { href: "/setup", label: "Setup" },
];

export default function BoardLayout({ children }: { children: React.ReactNode }) {
  const { store, session, demo } = useAppStore();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (demo === false && session === null) router.replace("/login");
  }, [demo, session, router]);

  // Desktop shell: questboard:// links (notifications, other apps) open the matching board.
  useEffect(() => onDeepLink((target) => router.push(targetToPath(target))), [router]);

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
        <PcNotifier />
        <MilestoneWatcher />
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
            <PushToggle />
            <NotifyTest />
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
