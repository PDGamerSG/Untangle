"use client";

import { ArrowUpRight, BrainCircuit, CheckCircle2, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { RepoSelect } from "./RepoSelect";
import { PulseRiskCard } from "./PulseRiskCard";
import { useRepo } from "./RepoContext";
import { EmptyState, ErrorState, Skeleton, SkeletonLines } from "./states";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";

function PulseSkeleton() {
  return <div className="grid gap-4 lg:grid-cols-2" role="status" aria-label="Loading knowledge risks">{[0, 1, 2].map((i) => <div className="card p-5" key={i}><Skeleton className="h-4 w-44" /><Skeleton className="mt-4 h-7 w-2/3" /><SkeletonLines rows={3} className="mt-4" /></div>)}</div>;
}

export function PulsePage() {
  const { repo } = useRepo();
  const res = useResource(repo ? `pulse:${repo}` : null, (signal) => api.pulse(repo!, signal));
  const data = res.data;
  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-3xl">
          <p className="eyebrow flex items-center gap-2 text-accent"><BrainCircuit size={14} aria-hidden /> Proactive repository memory</p>
          <h1 className="t-display mt-2 text-[2.2rem] leading-[1.04] text-ink sm:text-[2.8rem]">What is the team about to forget?</h1>
          <p className="mt-2 max-w-2xl text-[0.98rem] leading-relaxed text-ink-2">Pulse watches the graph for conflicts, drift and missing ownership, then shows the evidence behind each warning. It tells you where a handover or a decision review will pay off first.</p>
        </div>
        <RepoSelect compact />
      </header>

      {res.loading ? <PulseSkeleton /> : res.error ? <ErrorState title="Could not load the knowledge radar" error={res.error} onRetry={res.reload} /> : data ? (
        <>
          <section className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4" aria-label="Knowledge radar summary">
            <div className="pulse-stat card p-4"><p className="eyebrow text-ink-3">Coverage</p><p className="t-display mt-1 text-[2rem] text-ink">{Math.round(data.summary.coverage * 100)}%</p><p className="mt-1 text-[0.78rem] text-ink-2">decisions without a flagged risk</p></div>
            <div className="pulse-stat card p-4"><p className="eyebrow text-bad">Critical</p><p className="t-display mt-1 text-[2rem] text-ink">{data.summary.critical}</p><p className="mt-1 text-[0.78rem] text-ink-2">risks worth resolving first</p></div>
            <div className="pulse-stat card p-4"><p className="eyebrow text-accent">Drift</p><p className="t-display mt-1 text-[2rem] text-ink">{data.summary.drift}</p><p className="mt-1 text-[0.78rem] text-ink-2">decisions followed by code changes</p></div>
            <div className="pulse-stat card p-4"><p className="eyebrow text-warn">Ownership gaps</p><p className="t-display mt-1 text-[2rem] text-ink">{data.summary.ownership_gaps}</p><p className="mt-1 text-[0.78rem] text-ink-2">areas without a recent owner</p></div>
          </section>

          <section className="surface-soft flex flex-wrap items-center justify-between gap-3 p-4" aria-label="How Pulse scores risk">
            <div className="flex items-start gap-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent"><ShieldAlert size={15} aria-hidden /></span><div><p className="text-[0.86rem] font-semibold text-ink">Evidence first, score second</p><p className="mt-0.5 max-w-2xl text-[0.8rem] leading-relaxed text-ink-2">Contradictions rank highest, followed by code drift, ownership gaps, missing rationale and stale decisions. Every point links to a graph fact.</p></div></div>
            <Link href="/ask?question=what%20knowledge%20risks%20should%20I%20fix%20first%3F" className="btn btn-line btn-sm">Ask the graph <ArrowUpRight size={13} /></Link>
          </section>

          {data.risks.length ? <section aria-labelledby="risk-queue"><div className="mb-3 flex flex-wrap items-end justify-between gap-2"><div><p className="eyebrow text-ink-3">Priority queue</p><h2 id="risk-queue" className="t-display mt-1 text-[1.7rem] text-ink">Knowledge risks</h2></div><p className="t-num text-[0.8rem] text-ink-3">{data.summary.risks} flagged of {data.summary.active_decisions} active decisions</p></div><div className="grid gap-4 lg:grid-cols-2">{data.risks.map((risk) => <PulseRiskCard key={risk.id} risk={risk} />)}</div></section> : <EmptyState title="No knowledge risks surfaced"><span className="inline-flex items-center gap-1.5"><CheckCircle2 size={14} className="text-ok" aria-hidden /> The active decisions have enough ownership and evidence for now.</span></EmptyState>}
        </>
      ) : <EmptyState title="Choose an ingested repository to open Pulse" />}
    </div>
  );
}
