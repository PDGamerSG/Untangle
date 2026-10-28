"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useResource, useStoredValue } from "@/lib/hooks";
import type { RepoSummary } from "@/lib/types";

const STORAGE_KEY = "untangle.repo";

interface RepoState {
  repos: RepoSummary[] | undefined;
  loading: boolean;
  error: string | null;
  reload: () => void;
  /** The effective repo: the stored choice when it exists in the list, else the first repo. */
  repo: string | null;
  current: RepoSummary | undefined;
  setRepo: (fullName: string) => void;
}

const Ctx = createContext<RepoState | null>(null);

export function RepoProvider({ children }: { children: ReactNode }) {
  const res = useResource("repos", (signal) => api.repos(signal));
  const [stored, setStored] = useStoredValue(STORAGE_KEY);
  const value = useMemo<RepoState>(() => {
    const repos = res.data;
    const repo = repos && repos.length ? (stored && repos.some((r) => r.full_name === stored) ? stored : repos[0].full_name) : null;
    return {
      repos,
      loading: res.loading,
      error: res.error,
      reload: res.reload,
      repo,
      current: repos?.find((r) => r.full_name === repo),
      setRepo: setStored,
    };
  }, [res.data, res.loading, res.error, res.reload, stored, setStored]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useRepo(): RepoState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useRepo must be used inside RepoProvider");
  return v;
}
