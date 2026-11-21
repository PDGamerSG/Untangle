"use client";

import Link from "next/link";
import { useEffect } from "react";

/** Shown when a page fails to render. It never shows the raw error, which can contain internal details. */
export function PageError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <div role="alert" className="card-muted mx-auto my-10 max-w-lg p-6 text-[0.9rem] text-ink-2">
      <h1 className="t-display text-[1.4rem] text-ink">This page could not be shown.</h1>
      <p className="mt-1">Something unexpected happened while loading it. Retrying usually helps; your data is unchanged.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => retry()}>
          Try again
        </button>
        <Link href="/dashboard" className="btn btn-line btn-sm">
          Back to the dashboard
        </Link>
      </div>
    </div>
  );
}
