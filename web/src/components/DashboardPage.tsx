"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { GraphStatsPanel, SearchPanel } from "./GraphPanels";
import { EntityChip } from "./Chip";
import { RepoSelect } from "./RepoSelect";
import { useRepo } from "./RepoContext";
import { EmptyState, ErrorState, Skeleton, SkeletonLines } from "./states";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDateTime, fmtDuration } from "@/lib/format";
import { examplesFor } from "@/lib/examples";

function starters(repo: string) {
  const e = examplesFor(repo);
  return [e.trace, e.current, e.owner];
}

type Tone = "ok" | "warn" | "bad" | "idle";

function StatusRow({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  const dot = tone === "ok" ? "bg-ok" : tone === "warn" ? "bg-warn" : tone === "bad" ? "bg-bad" : "bg-ink-3";
  return (
    <div className="flex items-center justify-between gap-4 py-2.5 text-[0.88rem]">
      <dt className="flex items-center gap-2 text-ink-2">
        <span className={`inline-block h-2 w-2 rounded-full ${dot}`} aria-hidden />
        {label}
      </dt>
      <dd className="t-num min-w-0 truncate text-right text-ink">{value}</dd>
    </div>
  );
}

/** What is running behind the app, from `GET /health`. */
function SystemStatus() {
  const res = useResource("health", (signal) => api.health(signal));
  const d = res.data;
  return (
    <section aria-labelledby="status-heading">
      <div className="sec-head">
        <h2 id="status-heading">System status</h2>
        <button type="button" className="btn btn-ghost btn-sm -mr-2" onClick={res.reload}>
          Check again
        </button>
      </div>
      {res.loading ? (
        <SkeletonLines rows={4} />
      ) : res.error ? (
        <p className="text-[0.88rem] text-bad">The API is not reachable: {res.error}</p>
      ) : d ? (
        <dl className="divide-y divide-rule border-y border-rule">
          <StatusRow label="Graph database" value={d.neo4j?.version ? `Neo4j ${d.neo4j.version}${d.neo4j.aura ? " on AuraDB" : ""}` : "Not connected"} tone={d.ok ? "ok" : "bad"} />
          <StatusRow
            label="Answer model"
            value={d.llm.backend === "fake" ? "Deterministic answers" : `${d.llm.backend}${d.llm.model ? ` / ${d.llm.model}` : ""}`}
            tone={(d.llm.available ?? d.optional_backends?.llm.available) === false ? "warn" : "ok"}
          />
          <StatusRow
            label="Embeddings"
            value={`${d.embed.backend} (${d.embed.dim} dims)`}
            tone={(d.embed.available ?? d.optional_backends?.embeddings.available) === false ? "warn" : "ok"}
          />
          <StatusRow
            label="Speech and translation"
            value={(d.sarvam?.configured ?? d.optional_backends?.sarvam.configured) ? `Sarvam ${d.sarvam?.model ?? ""}`.trim() : "Not configured"}
            tone={(d.sarvam?.configured ?? d.optional_backends?.sarvam.configured) ? "ok" : "idle"}
          />
        </dl>
      ) : null}
    </section>
  );
}

function QuickAsk({ repo }: { repo: string }) {
  const router = useRouter();
  const [text, setText] = useState("");
  const open = (q: string) => router.push(`/ask?question=${encodeURIComponent(q)}`);
  return (
    <form
      className="card p-4 sm:p-5"
      onSubmit={(e) => {
        e.preventDefault();
        const q = text.trim();
        if (q) open(q);
      }}
    >
      <label htmlFor="dashboard-ask" className="text-[1rem] font-semibold text-ink">
        Ask {repo}
      </label>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          id="dashboard-ask"
          className="field flex-1 text-[1rem]"
          placeholder="Why is this config value set the way it is?"
          value={text}
          onChange={(e) => setText(e.target.value)}
          autoComplete="off"
        />
        <button type="submit" className="btn btn-primary sm:min-w-24" disabled={!text.trim()}>
          Ask
        </button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[0.82rem] text-ink-3" aria-label="Example questions">
        <span className="mr-0.5">Try</span>
        {starters(repo).map((q) => (
          <button key={q} type="button" className="example" onClick={() => open(q)}>
            {q}
          </button>
        ))}
      </div>
    </form>
  );
}

function TopRisks({ repo }: { repo: string }) {
  const res = useResource(`pulse:${repo}`, (signal) => api.pulse(repo, signal));
  const risks = res.data?.risks.slice(0, 3) ?? [];
  return (
    <section aria-labelledby="risks-heading">
      <div className="sec-head">
        <h2 id="risks-heading">Top knowledge risks</h2>
        <Link href="/pulse" className="sec-hint inline-flex items-center gap-0.5 font-semibold text-ink-2 underline-offset-4 hover:underline">
          Open Pulse <ArrowUpRight size={13} aria-hidden />
        </Link>
      </div>
      {res.loading ? (
        <SkeletonLines rows={3} />
      ) : res.error ? (
        <ErrorState title="Could not load Pulse" error={res.error} onRetry={res.reload} />
      ) : risks.length ? (
        <ol className="divide-y divide-rule border-y border-rule">
          {risks.map((r) => (
            <li key={r.id} className="py-3">
              <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                <EntityChip entity={r.entity} />
                <span className="t-num text-[0.8rem] text-ink-3">{Math.round(r.score * 100)}% risk</span>
              </div>
              <p className="mt-1.5 text-[0.86rem] leading-relaxed text-ink-2">{r.reasons[0]}</p>
              <Link href={`/pulse#${encodeURIComponent(r.id)}`} className="mt-1 inline-block text-[0.8rem] font-semibold text-ink-2 underline-offset-4 hover:underline">
                See the evidence
              </Link>
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-[0.88rem] text-ink-3">No knowledge risks right now.</p>
      )}
    </section>
  );
}

function RecentCalls({ repo }: { repo: string }) {
  const res = useResource(`meetings:${repo}`, (signal) => api.meetings(repo, signal));
  const calls = res.data?.slice(0, 3) ?? [];
  return (
    <section aria-labelledby="calls-heading">
      <div className="sec-head">
        <h2 id="calls-heading">Recent handover calls</h2>
        <Link href="/meetings" className="sec-hint inline-flex items-center gap-0.5 font-semibold text-ink-2 underline-offset-4 hover:underline">
          All calls <ArrowUpRight size={13} aria-hidden />
        </Link>
      </div>
      {res.loading ? (
        <SkeletonLines rows={3} />
      ) : res.error ? (
        <ErrorState title="Could not load handover calls" error={res.error} onRetry={res.reload} />
      ) : calls.length ? (
        <ol className="divide-y divide-rule border-y border-rule">
          {calls.map((m) => (
            <li key={m.id} className="py-3">
              <Link href={`/meetings/${encodeURIComponent(m.id)}`} className="text-[0.92rem] font-semibold text-ink underline-offset-4 hover:underline">
                {m.title}
              </Link>
              <p className="t-num mt-1 text-[0.8rem] text-ink-3">
                {fmtDateTime(m.started_at_iso)} · {fmtDuration(m.duration_ms)} · {m.decision_count} decisions
              </p>
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-[0.88rem] text-ink-3">
          No handover calls yet.{" "}
          <Link href="/meetings" className="font-semibold text-ink-2 underline underline-offset-4">
            Upload one
          </Link>
          .
        </p>
      )}
    </section>
  );
}

export function DashboardPage() {
  const { repo, loading, error, reload } = useRepo();
  return (
    <div className="space-y-12">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-3xl">
          <h1 className="t-display text-[2.2rem] leading-[1.04] text-ink sm:text-[2.8rem]">Dashboard</h1>
          <p className="mt-2 max-w-2xl text-[0.98rem] leading-relaxed text-ink-2">
            Ask a question, search what the graph knows, and see what needs attention. Everything here is read live from
            the Untangle API.
          </p>
        </div>
        <RepoSelect compact />
      </header>

      {loading ? (
        <div className="space-y-6" role="status" aria-label="Loading the dashboard">
          <Skeleton className="h-36" />
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
            <SkeletonLines rows={4} />
            <SkeletonLines rows={4} />
          </div>
        </div>
      ) : error ? (
        <ErrorState title="Could not load repositories" error={error} onRetry={reload} />
      ) : repo ? (
        <>
          <QuickAsk repo={repo} />

          <div className="grid grid-cols-1 gap-10 lg:grid-cols-2 lg:gap-12">
            <TopRisks repo={repo} />
            <RecentCalls repo={repo} />
          </div>

          <SearchPanel repo={repo} />
          <GraphStatsPanel repo={repo} />
          <SystemStatus />
        </>
      ) : (
        <EmptyState title="No repository has been ingested yet">
          Run <code className="t-code">uv run untangle ingest owner/name</code>, then reload this page.
        </EmptyState>
      )}
    </div>
  );
}
