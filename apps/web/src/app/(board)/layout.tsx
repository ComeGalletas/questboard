"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { StatusPill } from "@/components/StatusPill";
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

  useEffect(() => {
    if (session === null) router.replace("/login");
  }, [session, router]);

  if (!session) return null;

  return (
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
      <footer className="muted" style={{ marginTop: 24, fontSize: 14 }}>
        <button
          type="button"
          onClick={() => supabase?.auth.signOut()}
          style={{ all: "unset", cursor: "pointer", textDecoration: "underline" }}
        >
          Sign out
        </button>
      </footer>
    </div>
  );
}
