"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/hooks";
import { supabase } from "@/lib/supabase";

// Email + password rather than a magic link: on iOS a link opens Safari, not the installed PWA.
export default function LoginPage() {
  const session = useSession();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session) router.replace("/today");
  }, [session, router]);

  if (!supabase) {
    return (
      <main className="form panel">
        <h1 className="pixel" style={{ fontSize: 14 }}>
          Setup needed
        </h1>
        <p>
          Set <code>NEXT_PUBLIC_SUPABASE_URL</code> and <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code>{" "}
          (see <code>apps/web/.env.example</code>) and rebuild.
        </p>
      </main>
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (error) setError(error.message);
  }

  return (
    <form className="form panel" onSubmit={onSubmit}>
      <h1 className="pixel" style={{ fontSize: 14 }}>
        Questboard
      </h1>
      <input
        type="email"
        autoComplete="username"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <input
        type="password"
        autoComplete="current-password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <button type="submit" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}
