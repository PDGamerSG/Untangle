"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { useEffect, useState } from "react";
import { EntityChip } from "./Chip";
import { useRepo } from "./RepoContext";
import { EmptyState, ErrorState, Skeleton, SkeletonLines } from "./states";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDateTime } from "@/lib/format";
import { examplesFor } from "@/lib/examples";

/** What each node label means to someone browsing the graph. */
const LABEL_NAMES: Record<string, string> = {
  Commit: "commits",
  PullRequest: "pull requests",
  Issue: "issues",
  Comment: "review comments",
  Decision: "decisions",
  File: "files",
  Module: "modules",
  Symbol: "symbols",
  ConfigKey: "config keys",
  Dependency: "dependencies",
  Document: "documents",
  Chunk: "text passages",
  Meeting: "handover calls",
  Utterance: "call lines",
  Person: "people",
  Repo: "repositories",
};

function useDebounced(value: string, ms: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

export function GraphStatsPanel({ repo }: { repo: string }) {
  const { current } = useRepo();
  const res = useResource(`stats:${repo}`, (signal) => api.stats(repo, signal));
  const counts = current?.counts;
  const figures = counts
    ? [
        { label: "Commits", value: counts.commits },
        { label: "Pull requests", value: counts.prs },
        { label: "Issues", value: counts.issues },
        { label: "Decisions", value: counts.decisions },
        { label: "Handover calls", value: counts.meetings },
      ]
    : [];
  const labels = res.data ? Object.entries(res.data.labels).sort((a, b) => b[1] - a[1]) : [];
  const max = labels[0]?.[1] ?? 1;

  return (
    <section aria-labelledby="graph-heading" className="space-y-4">
      <div className="sec-head">
        <h2 id="graph-heading">What Untangle has read</h2>
        {current?.ingested_at_iso ? <p className="sec-hint t-num">Ingested {fmtDateTime(current.ingested_at_iso)}</p> : null}
      </div>

      {figures.length ? (
        <dl className="stat-strip grid-cols-2 sm:grid-cols-3 lg:grid-cols-5" aria-label="What was ingested">
          {figures.map((f) => (
            <div key={f.label}>
              <dt>{f.label}</dt>
              <dd className="t-num">{f.value.toLocaleString("en")}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {res.loading ? (
        <div role="status" aria-label="Loading graph statistics">
          <Skeleton className="h-4 w-48" />
          <SkeletonLines rows={4} className="mt-4" />
        </div>
      ) : res.error ? (
        <ErrorState title="Could not load graph statistics" error={res.error} onRetry={res.reload} />
      ) : res.data ? (
        <div>
          <p className="text-[0.9rem] text-ink-2">
            <span className="t-num font-semibold text-ink">{res.data.nodes.toLocaleString("en")}</span> nodes and{" "}
            <span className="t-num font-semibold text-ink">{res.data.relationships.toLocaleString("en")}</span> relationships in{" "}
            <span className="font-semibold text-ink">{repo}</span>.
          </p>
          <ul className="mt-3 space-y-2" aria-label="Nodes by type">
            {labels.map(([label, n]) => (
              <li key={label} className="grid grid-cols-[8.5rem_1fr_4.5rem] items-center gap-3 text-[0.84rem] sm:grid-cols-[9.5rem_1fr_4.5rem]">
                <span className="truncate text-ink-2">{LABEL_NAMES[label] ?? label}</span>
                <span className="h-1.5 overflow-hidden rounded-full bg-surface-3" aria-hidden>
                  <span className="block h-full rounded-full bg-accent" style={{ width: `${Math.max(1.5, (n / max) * 100)}%` }} />
                </span>
                <span className="t-num text-right text-ink">{n.toLocaleString("en")}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

export function SearchPanel({ repo }: { repo: string }) {
  const [text, setText] = useState("");
  const query = useDebounced(text.trim(), 250);
  const res = useResource(query ? `search:${repo}:${query}` : null, (signal) => api.search(repo, query, signal));
  const entities = res.data?.entities ?? [];
  const people = res.data?.people ?? [];

  return (
    <section aria-labelledby="search-heading" className="space-y-4">
      <div className="sec-head">
        <h2 id="search-heading">Search the graph</h2>
        <p className="sec-hint">Files, config keys, symbols, dependencies and people</p>
      </div>
      <div>
        <label htmlFor="explore-search" className="sr-only">
          Search {repo}
        </label>
        <input
          id="explore-search"
          type="search"
          className="field w-full text-[1rem]"
          placeholder="Try a config key, file name, symbol or dependency"
          value={text}
          onChange={(e) => setText(e.target.value)}
          autoComplete="off"
        />
        {!text ? (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[0.82rem] text-ink-3">
            <span className="mr-0.5">Try</span>
            {examplesFor(repo).search.map((s) => (
              <button key={s} type="button" className="example" onClick={() => setText(s)}>
                {s}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {!query ? null : res.loading ? (
        <SkeletonLines rows={4} />
      ) : res.error ? (
        <ErrorState title="Search failed" error={res.error} onRetry={res.reload} />
      ) : entities.length || people.length ? (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[2fr_1fr]">
          <ul className="divide-y divide-rule border-y border-rule" aria-label="Matching entities">
            {entities.map((e) => (
              <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div className="min-w-0">
                  <EntityChip entity={e} />
                  {e.path ? <p className="t-code mt-1 truncate text-[0.78rem] text-ink-3">{e.path}</p> : null}
                </div>
                <Link
                  href={`/ask?question=${encodeURIComponent(`why is ${e.name} like this?`)}`}
                  className="inline-flex items-center gap-0.5 text-[0.8rem] font-semibold text-ink-2 underline-offset-4 hover:underline"
                >
                  Ask why <ArrowUpRight size={13} aria-hidden />
                </Link>
              </li>
            ))}
            {!entities.length ? <li className="py-3 text-[0.86rem] text-ink-3">No files, keys or symbols match.</li> : null}
          </ul>
          <div>
            <h3 className="text-[0.88rem] font-semibold text-ink">People</h3>
            {people.length ? (
              <ul className="mt-2 divide-y divide-rule border-y border-rule">
                {people.map((p) => (
                  <li key={p.id} className="py-2.5 text-[0.9rem] text-ink">
                    {p.login ? (
                      <a href={`https://github.com/${p.login}`} target="_blank" rel="noreferrer" className="underline-offset-4 hover:underline">
                        {p.name ?? p.login}
                      </a>
                    ) : (
                      <span>{p.name}</span>
                    )}
                    {p.login && p.name ? <span className="t-code ml-2 text-ink-3">@{p.login}</span> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-[0.86rem] text-ink-3">No people match.</p>
            )}
          </div>
        </div>
      ) : (
        <EmptyState title={`Nothing in ${repo} matches “${query}”`}>Try a shorter name, or part of a file path.</EmptyState>
      )}
    </section>
  );
}
