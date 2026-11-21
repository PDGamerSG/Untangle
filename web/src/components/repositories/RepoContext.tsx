"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api";
import { useResource, useStoredValue } from "@/lib/hooks";
import type { RepoSummary } from "@/lib/types";

const STORAGE_KEY = "untangle.repo";
const DEFAULT_REPO = "PDGamerSG/Untangle";

interface RepoState {
  repos: RepoSummary[] | undefined;
  loading: boolean;
  error: string | null;
  reload: () => void;
  /** The saved choice, then this deployment's repository, then the first available repository. */
  repo: string | null;
  current: RepoSummary | undefined;
  setRepo: (fullName: string) => void;
}

const Ctx = createContext<RepoState | null>(null);

export function RepoProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  // Nothing is requested until the session is known, so a signed-out visitor never sees a failed request.
  const res = useResource(user ? "repos" : null, (signal) => api.repos(signal));
  const [stored, setStored] = useStoredValue(STORAGE_KEY);
  const value = useMemo<RepoState>(() => {
    const repos = res.data;
    const selected = repos?.find((r) => r.full_name === stored)
      ?? repos?.find((r) => r.full_name === DEFAULT_REPO)
      ?? repos?.[0];
    const repo = selected?.full_name ?? null;
    return {
      repos,
      loading: user === undefined || res.loading,
      error: res.error,
      reload: res.reload,
      repo,
      current: repos?.find((r) => r.full_name === repo),
      setRepo: setStored,
    };
  }, [user, res.data, res.loading, res.error, res.reload, stored, setStored]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useRepo(): RepoState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useRepo must be used inside RepoProvider");
  return v;
}
