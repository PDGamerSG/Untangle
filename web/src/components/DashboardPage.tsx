"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowUpRight, AudioLines, CalendarClock, MessageSquareText, Radar } from "lucide-react";
import { GraphStatsPanel, SearchPanel } from "./GraphPanels";
import { EntityChip } from "./Chip";
import { RepoSelect } from "./RepoSelect";
import { useRepo } from "./RepoContext";
import { EmptyState, ErrorState, Skeleton, SkeletonLines } from "./states";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDateTime, fmtDuration } from "@/lib/format";

const SHORTCUTS = [
  { href: "/ask", label: "Ask", text: "Ask why a value, file or dependency is the way it is.", icon: MessageSquareText },
  { href: "/timeline", label: "Timeline", text: "See which decisions were in force on any date.", icon: CalendarClock },
  { href: "/pulse", label: "Pulse", text: "Review contradictions, drift and ownership gaps.", icon: Radar },
  { href: "/meetings", label: "Meetings", text: "Upload a handover call and read what was decided.", icon: AudioLines },
] as const;

const STARTERS: Record<string, string[]> = {
  "knadh/listmonk": ["why is app.concurrency set the way it is?", "do we still use github.com/lib/pq?", "who should I ask about internal/manager?"],
};
const DEFAULT_STARTERS = ["why do we use neo4j in pyproject.toml?", "do we still use fastapi?", "who should I ask about src/untangle/answer?"];

type Tone = "ok" | "warn" | "bad" | "idle";

function StatusRow({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  const dot = tone === "ok" ? "bg-ok" : tone === "warn" ? "bg-warn" : tone === "bad" ? "bg-bad" : "bg-ink-3";
  return (
    <li className="flex items-center justify-between gap-3 py-2 text-[0.86rem]">
      <span className="flex items-center gap-2 text-ink-2">
        <span className={`inline-block h-2 w-2 rounded-full ${dot}`} aria-hidden />
        {label}
      </span>
      <span className="t-num truncate text-right text-ink">{value}</span>
    </li>
  );
}

/** What is running behind the app, from `GET /health`. */
function SystemStatus() {
  const res = useResource("health", (signal) => api.health(signal));
  const d = res.data;
  return (
    <section aria-labelledby="status-heading" className="card p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 id="status-heading" className="text-[0.95rem] font-semibold text-ink">
          System status
        </h2>
        <button type="button" className="btn btn-line btn-sm" onClick={res.reload}>
          Check again
        </button>
      </div>
      {res.loading ? (
        <SkeletonLines rows={4} className="mt-4" />
      ) : res.error ? (
        <p className="mt-3 text-[0.86rem] text-bad">The API is not reachable: {res.error}</p>
      ) : d ? (
        <ul className="mt-2 divide-y divide-rule">
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
        </ul>
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
      className="card flex flex-col gap-3 p-5"
      onSubmit={(e) => {
        e.preventDefault();
        const q = text.trim();
        if (q) open(q);
      }}
    >
      <label htmlFor="dashboard-ask" className="text-[0.95rem] font-semibold text-ink">
        Ask {repo}
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          id="dashboard-ask"
          className="field flex-1"
          placeholder="Why is this config value set the way it is?"
          value={text}
          onChange={(e) => setText(e.target.value)}
          autoComplete="off"
        />
        <button type="submit" className="btn btn-primary" disabled={!text.trim()}>
          Ask
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5" aria-label="Example questions">
        {(STARTERS[repo] ?? DEFAULT_STARTERS).map((q) => (
          <button key={q} type="button" className="btn btn-line btn-sm" onClick={() => open(q)}>
            {q}
          </button>
        ))}
      </div>
      <p className="text-[0.8rem] text-ink-3">The answer opens on the Ask page with its evidence, confidence and the person to ask.</p>
    </form>
  );
}

function TopRisks({ repo }: { repo: string }) {
  const res = useResource(`pulse:${repo}`, (signal) => api.pulse(repo, signal));
  const risks = res.data?.risks.slice(0, 3) ?? [];
  return (
    <section aria-labelledby="risks-heading" className="card p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 id="risks-heading" className="text-[0.95rem] font-semibold text-ink">
          Top knowledge risks
        </h2>
        <Link href="/pulse" className="inline-flex items-center gap-0.5 text-[0.8rem] font-semibold text-ink-2 underline-offset-4 hover:underline">
          Open Pulse <ArrowUpRight size={13} aria-hidden />
        </Link>
      </div>
      {res.loading ? (
        <SkeletonLines rows={3} className="mt-4" />
      ) : res.error ? (
        <ErrorState title="Could not load Pulse" error={res.error} onRetry={res.reload} />
      ) : risks.length ? (
        <ul className="mt-2 divide-y divide-rule">
          {risks.map((r) => (
            <li key={r.id} className="py-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <EntityChip entity={r.entity} />
                <span className="t-num text-[0.8rem] text-ink-3">{Math.round(r.score * 100)}% risk</span>
              </div>
              <p className="mt-1 text-[0.84rem] text-ink-2">{r.reasons[0]}</p>
              <Link href={`/pulse#${encodeURIComponent(r.id)}`} className="mt-1 inline-block text-[0.78rem] font-semibold text-ink-2 underline-offset-4 hover:underline">
                See the evidence
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-[0.86rem] text-ink-3">No knowledge risks right now.</p>
      )}
    </section>
  );
}

function RecentCalls({ repo }: { repo: string }) {
  const res = useResource(`meetings:${repo}`, (signal) => api.meetings(repo, signal));
  const calls = res.data?.slice(0, 3) ?? [];
  return (
    <section aria-labelledby="calls-heading" className="card p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 id="calls-heading" className="text-[0.95rem] font-semibold text-ink">
          Recent handover calls
        </h2>
        <Link href="/meetings" className="inline-flex items-center gap-0.5 text-[0.8rem] font-semibold text-ink-2 underline-offset-4 hover:underline">
          All calls <ArrowUpRight size={13} aria-hidden />
        </Link>
      </div>
      {res.loading ? (
        <SkeletonLines rows={3} className="mt-4" />
      ) : res.error ? (
        <ErrorState title="Could not load handover calls" error={res.error} onRetry={res.reload} />
      ) : calls.length ? (
        <ul className="mt-2 divide-y divide-rule">
          {calls.map((m) => (
            <li key={m.id} className="py-2.5">
              <Link href={`/meetings/${encodeURIComponent(m.id)}`} className="text-[0.9rem] font-semibold text-ink underline-offset-4 hover:underline">
                {m.title}
              </Link>
              <p className="t-num mt-0.5 text-[0.78rem] text-ink-3">
                {fmtDateTime(m.started_at_iso)} · {fmtDuration(m.duration_ms)} · {m.decision_count} decisions
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-[0.86rem] text-ink-3">
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
    <div className="space-y-10">
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
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2" role="status" aria-label="Loading the dashboard">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      ) : error ? (
        <ErrorState title="Could not load repositories" error={error} onRetry={reload} />
      ) : repo ? (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[3fr_2fr]">
            <QuickAsk repo={repo} />
            <SystemStatus />
          </div>

          <nav aria-label="Dashboard shortcuts" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {SHORTCUTS.map(({ href, label, text, icon: Icon }) => (
              <Link key={href} href={href} className="card group flex flex-col gap-2 p-4 transition-colors hover:border-rule-strong">
                <span className="flex items-center justify-between">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-soft text-accent">
                    <Icon size={15} aria-hidden />
                  </span>
                  <ArrowUpRight size={15} className="text-ink-3 transition-colors group-hover:text-ink" aria-hidden />
                </span>
                <span className="text-[0.95rem] font-semibold text-ink">{label}</span>
                <span className="text-[0.82rem] leading-relaxed text-ink-2">{text}</span>
              </Link>
            ))}
          </nav>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <TopRisks repo={repo} />
            <RecentCalls repo={repo} />
          </div>

          <SearchPanel repo={repo} />
          <GraphStatsPanel repo={repo} />
        </>
      ) : (
        <EmptyState title="No repository has been ingested yet">
          Run <code className="t-code">uv run untangle ingest owner/name</code>, then reload this page.
        </EmptyState>
      )}
    </div>
  );
}
