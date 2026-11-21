"use client";

import { useEffect, type ReactNode } from "react";
import { useAuth } from "./AuthProvider";

/**
 * The workspace needs a session. A stale or revoked cookie passes the optimistic proxy check, so once the session
 * check answers "signed out" the visitor goes to sign-in and comes back here afterwards.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, error } = useAuth();
  useEffect(() => {
    if (user === null && !error) {
      const here = window.location.pathname + window.location.search;
      window.location.replace(`/login?next=${encodeURIComponent(here)}`);
    }
  }, [user, error]);
  if (user === null && error) {
    return (
      <div role="alert" className="card-muted mx-auto mt-10 max-w-lg p-6 text-[0.9rem] text-ink-2">
        <p className="font-semibold text-ink">Untangle could not check your session.</p>
        <p className="mt-1">{error}</p>
        <button type="button" className="btn btn-line btn-sm mt-3" onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }
  return <>{children}</>;
}
