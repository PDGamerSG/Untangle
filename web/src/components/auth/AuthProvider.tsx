"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, SAMPLE_MODE } from "@/lib/api";
import { clearResources } from "@/lib/hooks";
import type { Account } from "@/lib/types";

interface AuthState {
  /** undefined while the session is being checked, null when signed out. */
  user: Account | null | undefined;
  error: string | null;
  refresh: () => Promise<void>;
  setUser: (user: Account | null) => void;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);
const SAMPLE_USER: Account = { id: "user:sample", email: "sample@untangle.local", name: "Sample visitor", role: "member", created_at_iso: "2026-11-01T00:00:00Z" };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<Account | null | undefined>(SAMPLE_MODE ? SAMPLE_USER : undefined);
  const [error, setError] = useState<string | null>(null);

  const check = useCallback(() => {
    if (SAMPLE_MODE) return Promise.resolve();
    return api.me().then(
      (me) => {
        setUserState(me.user);
        setError(null);
      },
      (e: unknown) => {
        setUserState(null);
        // A 401 means signed out. Anything else means the service is unreachable: say so instead of signing out.
        setError(e instanceof ApiError && e.status === 401 ? null : e instanceof Error ? e.message : String(e));
      },
    );
  }, []);
  const refresh = check;

  useEffect(() => {
    void check();
  }, [check]);

  const setUser = useCallback((next: Account | null) => {
    // Another account's cached answers must never be shown to this one.
    clearResources();
    setUserState(next);
    setError(null);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      clearResources({ refetch: false });
      setUserState(null);
      // A full page load drops every client-side cache that belonged to the signed-out account.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login");
    }
  }, []);

  const value = useMemo(() => ({ user, error, refresh, setUser, signOut }), [user, error, refresh, setUser, signOut]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}

/** Only same-site paths are followed after sign-in, so a crafted link cannot send someone to another site. */
export function safeNext(value: string | null | undefined, fallback = "/repositories"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\") || value.startsWith("/login") || value.startsWith("/signup")) return fallback;
  return value;
}
