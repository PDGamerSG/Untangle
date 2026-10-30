"use client";

import Link from "next/link";
import { ArrowUpRight, Database, Search, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { EntityChip } from "./Chip";
import { RepoSelect } from "./RepoSelect";
import { useRepo } from "./RepoContext";
import { EmptyState, ErrorState, Skeleton, SkeletonLines } from "./states";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDateTime } from "@/lib/format";

const SUGGESTIONS = ["neo4j", "concurrency", "docker-compose.yml", "README.md", "config"];

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

function GraphStatsPanel({ repo }: { repo: string }) {
  const { current } = useRepo();
  const res = useResource(`stats:${repo}`, (signal) => api.stats(repo, signal));
  const counts = current?.counts;
  const tiles = counts
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
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="eyebrow flex items-center gap-2 text-ink-3">
            <Database size={13} aria-hidden /> What Untangle has read
          </p>
          <h2 id="graph-heading" className="t-display mt-1 text-[1.7rem] text-ink">
            The graph behind every answer
          </h2>
        </div>
        {current?.ingested_at_iso ? <p className="t-num text-[0.8rem] text-ink-3">Ingested {fmtDateTime(current.ingested_at_iso)}</p> : null}
      </div>

      {tiles.length ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {tiles.map((t) => (
            <div key={t.label} className="card p-4">
              <p className="eyebrow text-ink-3">{t.label}</p>
              <p className="t-display t-num mt-1 text-[1.8rem] text-ink">{t.value.toLocaleString("en")}</p>
            </div>
          ))}
        </div>
      ) : null}

      {res.loading ? (
        <div className="card p-5" role="status" aria-label="Loading graph statistics">
          <Skeleton className="h-4 w-48" />
          <SkeletonLines rows={4} className="mt-4" />
        </div>
      ) : res.error ? (
        <ErrorState title="Could not load graph statistics" error={res.error} onRetry={res.reload} />
      ) : res.data ? (
        <div className="card p-5">
          <p className="text-[0.9rem] text-ink-2">
            <span className="t-num font-semibold text-ink">{res.data.nodes.toLocaleString("en")}</span> nodes and{" "}
            <span className="t-num font-semibold text-ink">{res.data.relationships.toLocaleString("en")}</span> relationships in{" "}
            <span className="font-semibold text-ink">{repo}</span>.
          </p>
          <ul className="mt-4 space-y-2" aria-label="Nodes by type">
            {labels.map(([label, n]) => (
              <li key={label} className="grid grid-cols-[9.5rem_1fr_4.5rem] items-center gap-3 text-[0.84rem]">
                <span className="truncate text-ink-2">{LABEL_NAMES[label] ?? label}</span>
                <span className="h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                  <span className="block h-full rounded-full bg-accent" style={{ width: `${Math.max(2, (n / max) * 100)}%` }} />
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

function SearchPanel({ repo }: { repo: string }) {
  const [text, setText] = useState("");
  const query = useDebounced(text.trim(), 250);
  const res = useResource(query ? `search:${repo}:${query}` : null, (signal) => api.search(repo, query, signal));
  const entities = res.data?.entities ?? [];
  const people = res.data?.people ?? [];

  return (
    <section aria-labelledby="search-heading" className="space-y-4">
      <div>
        <p className="eyebrow flex items-center gap-2 text-ink-3">
          <Search size={13} aria-hidden /> Search the graph
        </p>
        <h2 id="search-heading" className="t-display mt-1 text-[1.7rem] text-ink">
          Find a file, key, dependency or person
        </h2>
      </div>
      <div className="card p-4">
        <label htmlFor="explore-search" className="sr-only">
          Search {repo}
        </label>
        <input
          id="explore-search"
          type="search"
          className="field w-full"
          placeholder="Try a config key, file name, symbol or dependency"
          value={text}
          onChange={(e) => setText(e.target.value)}
          autoComplete="off"
        />
        {!text ? (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[0.8rem] text-ink-3">
            <span>Try</span>
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="btn btn-line btn-sm" onClick={() => setText(s)}>
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
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <div className="card divide-y divide-rule">
            {entities.map((e) => (
              <div key={e.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
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
              </div>
            ))}
            {!entities.length ? <p className="px-4 py-3 text-[0.86rem] text-ink-3">No files, keys or symbols match.</p> : null}
          </div>
          <div className="card p-4">
            <p className="eyebrow text-ink-3">People</p>
            {people.length ? (
              <ul className="mt-2 space-y-2">
                {people.map((p) => (
                  <li key={p.id} className="flex items-center gap-2 text-[0.9rem] text-ink">
                    <UserRound size={14} className="text-ink-3" aria-hidden />
                    {p.login ? (
                      <a href={`https://github.com/${p.login}`} target="_blank" rel="noreferrer" className="underline-offset-4 hover:underline">
                        {p.name ?? p.login}
                      </a>
                    ) : (
                      <span>{p.name}</span>
                    )}
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

export function ExplorePage() {
  const { repo } = useRepo();
  return (
    <div className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-3xl">
          <p className="eyebrow text-accent">Graph explorer</p>
          <h1 className="t-display mt-2 text-[2.2rem] leading-[1.04] text-ink sm:text-[2.8rem]">Explore the repository’s memory</h1>
          <p className="mt-2 max-w-2xl text-[0.98rem] leading-relaxed text-ink-2">
            Search everything Untangle extracted from the history, open any file, key or dependency to see the decisions
            about it, and check how much of the repository the graph covers.
          </p>
        </div>
        <RepoSelect compact />
      </header>
      {repo ? (
        <>
          <SearchPanel repo={repo} />
          <GraphStatsPanel repo={repo} />
        </>
      ) : (
        <EmptyState title="Choose an ingested repository to explore" />
      )}
    </div>
  );
}
