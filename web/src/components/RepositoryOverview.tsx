"use client";

import Link from "next/link";
import { Activity, AlertTriangle, ArrowUpRight, AudioLines, ExternalLink, FileText, History, MessageCircleQuestion, Network, Package, Puzzle } from "lucide-react";
import { EmptyState, ErrorState, SkeletonLines } from "./states";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDay } from "@/lib/format";
import { hasCuratedExamples } from "@/lib/examples";
import type { RepositoryOverview } from "@/lib/types";

/** Labels for the inventory counts, in reading order. Keys the API does not send are skipped, never shown as zero. */
const COUNT_LABELS: [key: string, label: string][] = [
  ["files", "File paths"],
  ["current_files", "Current files"],
  ["modules", "Modules"],
  ["symbols", "Symbols"],
  ["config_keys", "Config keys"],
  ["dependencies", "Dependencies"],
  ["documents", "Documents"],
  ["features", "Features"],
  ["commits", "Commits"],
  ["prs", "Pull requests"],
  ["issues", "Issues"],
  ["decisions", "Decisions"],
  ["people", "Contributors"],
  ["meetings", "Handover calls"],
];
const COMPACT_KEYS = ["files", "current_files", "dependencies", "documents", "features", "decisions", "people"];

export function useOverview(repo: string | null) {
  return useResource(repo ? `overview:${repo}` : null, (signal) => api.repositoryOverview(repo!, signal));
}

/**
 * Example questions for `repo`: the curated list when there is one, otherwise up to `n` of the questions the API
 * suggests from the repository's own records, otherwise `fallback`.
 */
export function useStarterQuestions(repo: string | null, fallback: string[], n = 3): string[] {
  const curated = hasCuratedExamples(repo);
  const res = useOverview(curated ? null : repo);
  const suggested = res.data?.suggested_questions ?? [];
  return !curated && suggested.length ? suggested.slice(0, n) : fallback;
}

function Counts({ data, keys }: { data: RepositoryOverview; keys?: string[] }) {
  const rows = COUNT_LABELS.filter(([k]) => typeof data.counts[k] === "number" && (!keys || keys.includes(k)));
  if (!rows.length) return null;
  return (
    <dl className="stat-strip grid-cols-2 sm:grid-cols-3 lg:grid-cols-6" aria-label="Indexed records">
      {rows.map(([k, label]) => (
        <div key={k}>
          <dt>{label}</dt>
          <dd className="t-num">{data.counts[k].toLocaleString()}</dd>
        </div>
      ))}
    </dl>
  );
}

function Facts({ data }: { data: RepositoryOverview }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[0.82rem] text-ink-3">
      {data.languages.length ? (
        <span className="flex flex-wrap items-center gap-1.5" aria-label="Languages">
          {data.languages.map((l) => (
            <span key={l} className="chip" data-kind="entity">
              {l}
            </span>
          ))}
        </span>
      ) : null}
      {data.head_sha ? (
        <span className="t-num">
          Branch <code className="t-code text-ink-2">{data.default_branch ?? "unknown"}</code> at <code className="t-code text-ink-2">{data.head_sha.slice(0, 7)}</code>
        </span>
      ) : (
        <span className="text-ink-3">Git history not indexed</span>
      )}
      {data.ingested_at_iso ? <span>Indexed {fmtDay(data.ingested_at_iso)}</span> : null}
      {data.url && /^https?:\/\//.test(data.url) ? (
        <a href={data.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-semibold text-ink-2 underline-offset-4 hover:underline">
          GitHub <ExternalLink size={12} aria-hidden />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      ) : null}
    </div>
  );
}

/** What the index may have left out, from the coverage block and the API's own warnings. */
function Coverage({ data }: { data: RepositoryOverview }) {
  const c = data.coverage;
  const notes: string[] = [];
  if (c.max_commits != null && c.commits >= c.max_commits) notes.push(`History covers the most recent ${c.max_commits.toLocaleString()} commits.`);
  if (c.max_prs != null) notes.push(`Up to ${c.max_prs.toLocaleString()} pull requests are read.`);
  if (c.max_issues != null) notes.push(`Up to ${c.max_issues.toLocaleString()} issues are read.`);
  if (c.map_scanned_files) notes.push(`The map scanned ${c.map_scanned_files.toLocaleString()} files.`);
  if (c.unresolved_imports) notes.push(`${c.unresolved_imports.toLocaleString()} imports could not be resolved to a file.`);
  if (!notes.length && !data.warnings.length) return null;
  return (
    <section aria-labelledby="coverage-heading" className="card-muted p-4">
      <h3 id="coverage-heading" className="text-[0.9rem] font-semibold text-ink">
        What the index covers
      </h3>
      {notes.length ? <p className="mt-1 text-[0.84rem] leading-relaxed text-ink-2">{notes.join(" ")}</p> : null}
      {data.warnings.length ? (
        <ul className="mt-2 space-y-1">
          {data.warnings.map((w) => (
            <li key={w} className="flex gap-2 text-[0.84rem] leading-relaxed text-ink-2">
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-warn" aria-hidden />
              {w}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function Shown({ shown, total, noun }: { shown: number; total: number | undefined; noun: string }) {
  if (total != null && total > shown) return <span className="sec-hint t-num">First {shown} of {total.toLocaleString()} {noun}</span>;
  return <span className="sec-hint t-num">{shown.toLocaleString()} {noun}</span>;
}

export function SuggestedQuestions({ questions }: { questions: string[] }) {
  if (!questions.length) return null;
  return (
    <section aria-labelledby="suggested-heading">
      <div className="sec-head">
        <h3 id="suggested-heading">Questions this repository can answer</h3>
        <span className="sec-hint">Suggested from its indexed records</span>
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {questions.map((q) => (
          <li key={q} className="max-w-full">
            <Link href={`/ask?question=${encodeURIComponent(q)}`} className="example gap-1.5">
              <MessageCircleQuestion size={14} className="shrink-0 text-accent" aria-hidden />
              {q}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

const TOOLS = [
  { href: "/ask", label: "Ask", hint: "Why a value, file or dependency is the way it is", icon: MessageCircleQuestion },
  { href: "/map", label: "Map", hint: "Features, files and what a commit could affect", icon: Network },
  { href: "/timeline", label: "Timeline", hint: "What was decided, and what replaced it", icon: History },
  { href: "/pulse", label: "Pulse", hint: "Conflicts, drift and ownership gaps", icon: Activity },
  { href: "/meetings", label: "Meetings", hint: "Handover calls linked to the code", icon: AudioLines },
] as const;

function Tools() {
  return (
    <nav aria-label="Tools for this repository" className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-5">
      {TOOLS.map(({ href, label, hint, icon: Icon }) => (
        <Link key={href} href={href} className="card group flex items-start gap-3 p-3 transition-colors hover:border-accent/40 hover:bg-accent-soft/40">
          <span className="rounded-md bg-accent-soft p-1.5 text-accent">
            <Icon size={16} aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block text-[0.88rem] font-semibold text-ink">{label}</span>
            <span className="block text-[0.78rem] leading-snug text-ink-3">{hint}</span>
          </span>
        </Link>
      ))}
    </nav>
  );
}

function Inventory({ data }: { data: RepositoryOverview }) {
  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
      <section aria-labelledby="features-heading" className="min-w-0">
        <div className="sec-head">
          <h3 id="features-heading" className="flex items-center gap-1.5">
            <Puzzle size={15} className="text-accent" aria-hidden /> Features
          </h3>
          <Shown shown={data.features.length} total={data.counts.features} noun="features" />
        </div>
        {data.features.length ? (
          <ul className="divide-y divide-rule border-y border-rule">
            {data.features.map((f) => (
              <li key={f.id} className="py-2.5">
                <p className="break-words text-[0.88rem] font-semibold text-ink">{f.name}</p>
                <p className="mt-0.5 break-words text-[0.76rem] text-ink-3">
                  {f.source}
                  {f.entrypoints.length ? (
                    <>
                      {" · "}
                      <code className="t-code">{f.entrypoints.slice(0, 2).join(", ")}</code>
                      {f.entrypoints.length > 2 ? ` +${f.entrypoints.length - 2}` : ""}
                    </>
                  ) : null}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[0.85rem] text-ink-3">No features were detected.</p>
        )}
        {data.features.length ? (
          <Link href="/map" className="mt-2 inline-flex items-center gap-1 text-[0.8rem] font-semibold text-accent underline-offset-4 hover:underline">
            See them on the map <ArrowUpRight size={13} aria-hidden />
          </Link>
        ) : null}
      </section>

      <section aria-labelledby="deps-heading" className="min-w-0">
        <div className="sec-head">
          <h3 id="deps-heading" className="flex items-center gap-1.5">
            <Package size={15} className="text-accent" aria-hidden /> Dependencies
          </h3>
          <Shown shown={data.dependencies.length} total={data.counts.dependencies} noun="dependencies" />
        </div>
        {data.dependencies.length ? (
          <ul className="max-h-[26rem] divide-y divide-rule overflow-y-auto border-y border-rule">
            {data.dependencies.map((d) => (
              <li key={d.id} className="flex items-baseline justify-between gap-3 py-2">
                <span className="min-w-0">
                  <code className="t-code block break-all text-ink">{d.name}</code>
                  <span className="block truncate text-[0.74rem] text-ink-3" title={d.path}>
                    {d.ecosystem} · {d.path}
                  </span>
                </span>
                {d.version ? <span className="t-num shrink-0 text-[0.76rem] text-ink-2">{d.version}</span> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[0.85rem] text-ink-3">No dependency manifests were found.</p>
        )}
      </section>

      <section aria-labelledby="docs-heading" className="min-w-0">
        <div className="sec-head">
          <h3 id="docs-heading" className="flex items-center gap-1.5">
            <FileText size={15} className="text-accent" aria-hidden /> Documents
          </h3>
          <Shown shown={data.documents.length} total={data.counts.documents} noun="documents" />
        </div>
        {data.documents.length ? (
          <ul className="max-h-[26rem] divide-y divide-rule overflow-y-auto border-y border-rule">
            {data.documents.map((d) => (
              <li key={d.id} className="py-2">
                <span className="block break-words text-[0.86rem] text-ink">{d.title || d.path}</span>
                {d.title ? <code className="t-code block break-all text-ink-3">{d.path}</code> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[0.85rem] text-ink-3">No documentation files were found.</p>
        )}
      </section>
    </div>
  );
}

/**
 * The indexed inventory of one repository. `compact` is the dashboard summary; the full view adds the feature,
 * dependency and document lists, coverage notes and links to every tool.
 */
export function RepositoryOverviewPanel({ repo, compact = false }: { repo: string; compact?: boolean }) {
  const res = useOverview(repo);
  const data = res.data;
  if (res.loading) return <SkeletonLines rows={compact ? 3 : 5} />;
  if (res.error) {
    if (res.errorStatus === 404)
      return (
        <EmptyState title="No inventory for this repository yet">
          It appears after the repository is indexed or re-indexed with the current version of Untangle.
        </EmptyState>
      );
    return <ErrorState title="Could not load the repository inventory" error={res.error} onRetry={res.reload} />;
  }
  if (!data) return null;
  if (compact)
    return (
      <div className="space-y-3">
        {data.description ? <p className="max-w-3xl text-[0.92rem] leading-relaxed text-ink-2">{data.description}</p> : null}
        <Facts data={data} />
        <Counts data={data} keys={COMPACT_KEYS} />
      </div>
    );
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <p className="max-w-3xl text-[0.98rem] leading-relaxed text-ink-2">
          {data.description ?? <span className="text-ink-3">This repository has no description on GitHub.</span>}
        </p>
        <Facts data={data} />
      </div>
      <Counts data={data} />
      <SuggestedQuestions questions={data.suggested_questions} />
      <Tools />
      <Inventory data={data} />
      <Coverage data={data} />
    </div>
  );
}
