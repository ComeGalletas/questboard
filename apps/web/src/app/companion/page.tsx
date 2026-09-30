"use client";

// The desktop companion window's page (apps/desktop opens it in a transparent overlay). It
// shares the dashboard's sign-in (same WebView storage); signed out, it shows nothing.

import { useEffect } from "react";
import { Companion } from "@/components/Companion";
import { LogProvider } from "@/data/log";
import { ReactionProvider } from "@/data/reaction";
import { useAppStore } from "@/data/use-app-store";

export default function Page() {
  const { store } = useAppStore();

  useEffect(() => {
    document.documentElement.classList.add("companion-root");
    return () => document.documentElement.classList.remove("companion-root");
  }, []);

  if (!store) return null;
  return (
    <LogProvider store={store}>
      <ReactionProvider>
        <Companion />
      </ReactionProvider>
    </LogProvider>
  );
}
