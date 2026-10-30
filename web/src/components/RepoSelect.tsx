"use client";

import { useId } from "react";
import { useRepo } from "./RepoContext";
import { fmtDay } from "@/lib/format";

export function RepoSelect({ compact = false }: { compact?: boolean }) {
  const { repos, repo, setRepo, loading, error, reload, current } = useRepo();
  const id = useId();
  if (loading)
    return (
      <div className={compact ? "h-9 w-56 skeleton" : "h-10 w-full max-w-xs skeleton"} role="status" aria-label="Loading repositories" />
    );
  if (error)
    return (
      <p role="alert" className="text-[0.85rem] text-bad">
        Could not load repositories: {error}{" "}
        <button type="button" onClick={reload} className="underline">
          Retry
        </button>
      </p>
    );
  if (!repos?.length)
    return (
      <p className="text-[0.85rem] text-ink-3">
        No repositories ingested yet. Run <code className="t-code">untangle ingest owner/name</code>.
      </p>
    );
  return (
    <div className={compact ? "flex min-w-0 max-w-full items-center gap-2" : "flex flex-col gap-1"}>
      <label htmlFor={id} className="text-[0.78rem] font-semibold uppercase tracking-wider text-ink-3">
        Repository
      </label>
      <select id={id} value={repo ?? ""} onChange={(e) => setRepo(e.target.value)} className={`field ${compact ? "h-9 min-w-0 max-w-full w-auto py-1" : "max-w-xs"}`}>
        {repos.map((r) => (
          <option key={r.full_name} value={r.full_name}>
            {r.full_name}
          </option>
        ))}
      </select>
      {!compact && current ? (
        <p className="t-num text-[0.78rem] text-ink-3">
          {current.counts.commits.toLocaleString()} commits · {current.counts.prs.toLocaleString()} PRs · {current.counts.issues.toLocaleString()} issues ·{" "}
          {current.counts.decisions.toLocaleString()} decisions · {current.counts.meetings} meeting{current.counts.meetings === 1 ? "" : "s"} · ingested{" "}
          {fmtDay(current.ingested_at_iso)}
        </p>
      ) : null}
    </div>
  );
}
