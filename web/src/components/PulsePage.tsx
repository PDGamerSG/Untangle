"use client";

import { CheckCircle2 } from "lucide-react";
import { RepoSelect } from "./RepoSelect";
import { PulseQueue } from "./PulseQueue";
import { useRepo } from "./RepoContext";
import { EmptyState, ErrorState, Skeleton, SkeletonLines } from "./states";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";

function PulseSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-2" role="status" aria-label="Loading knowledge risks">
      {[0, 1, 2].map((i) => (
        <div className="card p-5" key={i}>
          <Skeleton className="h-4 w-44" />
          <Skeleton className="mt-4 h-7 w-2/3" />
          <SkeletonLines rows={3} className="mt-4" />
        </div>
      ))}
    </div>
  );
}

export function PulsePage() {
  const { repo } = useRepo();
  const res = useResource(repo ? `pulse:${repo}` : null, (signal) => api.pulse(repo!, signal));
  const data = res.data;
  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-3xl">
          <h1 className="t-display text-[2.2rem] leading-[1.04] text-ink sm:text-[2.8rem]">What is the team about to forget?</h1>
          <p className="mt-2 max-w-2xl text-[0.98rem] leading-relaxed text-ink-2">
            Pulse watches the graph for conflicts, drift and missing ownership, then shows the evidence behind each warning. Contradictions rank
            highest, followed by code drift, ownership gaps, missing rationale and stale decisions.
          </p>
        </div>
        <RepoSelect compact />
      </header>

      {res.loading ? (
        <PulseSkeleton />
      ) : res.error ? (
        <ErrorState title="Could not load the knowledge radar" error={res.error} onRetry={res.reload} />
      ) : data ? (
        <>
          <dl className="stat-strip grid-cols-2 lg:grid-cols-4" aria-label="Knowledge radar summary">
            <div>
              <dt>Returned risks</dt>
              <dd className="t-num">{data.risks.length}</dd>
              <p className="mt-1 text-[0.78rem] text-ink-2">in the current priority queue</p>
            </div>
            <div>
              <dt className="text-bad">Critical</dt>
              <dd className="t-num">{data.summary.critical}</dd>
              <p className="mt-1 text-[0.78rem] text-ink-2">risks worth resolving first</p>
            </div>
            <div>
              <dt>Drift</dt>
              <dd className="t-num">{data.summary.drift}</dd>
              <p className="mt-1 text-[0.78rem] text-ink-2">decisions followed by code changes</p>
            </div>
            <div>
              <dt className="text-warn">Ownership gaps</dt>
              <dd className="t-num">{data.summary.ownership_gaps}</dd>
              <p className="mt-1 text-[0.78rem] text-ink-2">areas without a recent owner</p>
            </div>
          </dl>

          {data.risks.length ? (
            <PulseQueue key={repo} repo={repo!} data={data} />
          ) : (
            <EmptyState title="No knowledge risks surfaced">
              <span className="inline-flex items-center gap-1.5">
                <CheckCircle2 size={14} className="text-ok" aria-hidden /> No risks were returned by this scan. Explore the timeline to inspect the recorded decisions.
              </span>
            </EmptyState>
          )}
        </>
      ) : (
        <EmptyState title="Choose an ingested repository to open Pulse" />
      )}
    </div>
  );
}
