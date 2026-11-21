"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { ExternalLink, LoaderCircle, RefreshCw } from "lucide-react";
import { ErrorState, SkeletonLines } from "@/components/ui/states";
import { api, API_BASE, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDay, fmtRelative } from "@/lib/format";
import type { GitHubIdentity, GitHubRepository, ImportJob, RepositoryChanges, SavedRepository } from "@/lib/types";

const STATUS: Record<string, string> = { queued: "Queued", running: "Indexing", complete: "Indexed", failed: "Failed" };

function connectHref(): string {
  return `${API_BASE}/auth/github/start?next=${encodeURIComponent("/repositories")}`;
}

function Changes({ repo }: { repo: string }) {
  const changes = useResource(`changes:${repo}`, (signal) => api.repositoryChanges(repo, signal));
  if (changes.loading) return <SkeletonLines rows={3} />;
  if (changes.error) return <ErrorState title="Could not load changes" error={changes.error} onRetry={changes.reload} />;
  const data = changes.data as RepositoryChanges | undefined;
  if (!data) return null;
  return (
    <div className="mt-3 space-y-4 border-l-2 border-rule pl-4">
      {!data.available ? (
        <p className="text-[0.84rem] text-ink-2">{data.reason}</p>
      ) : data.ahead_by ? (
        <div>
          <p className="text-[0.84rem] text-ink-2">
            <span className="t-num font-semibold text-ink">{data.ahead_by}</span> commit{data.ahead_by === 1 ? "" : "s"} on{" "}
            <code className="t-code">{data.default_branch}</code> since the indexed version{" "}
            <code className="t-code">{data.indexed_sha.slice(0, 7)}</code>
            {data.files_changed ? <>, touching <span className="t-num">{data.files_changed}</span> files</> : null}.
            {data.compare_url ? (
              <>
                {" "}
                <a href={data.compare_url} target="_blank" rel="noreferrer" className="font-semibold text-accent underline-offset-4 hover:underline">
                  Compare on GitHub
                </a>
              </>
            ) : null}
          </p>
          <ul className="mt-2 divide-y divide-rule border-y border-rule">
            {(data.commits ?? []).map((c) => (
              <li key={c.sha} className="flex flex-wrap items-baseline justify-between gap-x-3 py-1.5 text-[0.84rem]">
                <span className="min-w-0">
                  <a href={c.url} target="_blank" rel="noreferrer" className="t-code mr-2 text-accent">
                    {c.short}
                  </a>
                  <span className="text-ink">{c.message}</span>
                </span>
                <span className="t-num shrink-0 text-[0.76rem] text-ink-3">
                  {c.author}
                  {c.date ? ` · ${fmtDay(c.date)}` : ""}
                </span>
              </li>
            ))}
          </ul>
          {data.files?.length ? (
            <details className="mt-2 text-[0.82rem]">
              <summary className="cursor-pointer font-semibold text-ink-2">Changed files</summary>
              <ul className="mt-1 space-y-0.5">
                {data.files.map((f) => (
                  <li key={f.path} className="t-num flex justify-between gap-3">
                    <code className="t-code break-all">{f.path}</code>
                    <span className="shrink-0 text-ink-3">
                      {f.status} +{f.additions} −{f.deletions}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      ) : (
        <p className="text-[0.84rem] text-ink-2">Up to date: GitHub has no commits after the indexed version.</p>
      )}
      {data.indexed_recent.length ? (
        <div>
          <p className="text-[0.8rem] font-semibold text-ink-2">Latest indexed commits</p>
          <ul className="mt-1 space-y-0.5 text-[0.82rem]">
            {data.indexed_recent.map((c) => (
              <li key={c.sha} className="flex gap-2">
                <code className="t-code shrink-0 text-ink-3">{c.short}</code>
                <span className="min-w-0 truncate text-ink">{c.message}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function SavedRow({
  r,
  selected,
  onUse,
  onQueued,
  onChanged,
}: {
  r: SavedRepository;
  selected: boolean;
  onUse: (repo: string) => void;
  onQueued: (job: ImportJob) => void;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<"import" | "remove" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ahead = r.changes?.available ? (r.changes.ahead_by ?? 0) : 0;
  const pending = r.job && (r.job.status === "queued" || r.job.status === "running");

  async function reimport() {
    setBusy("import");
    setError(null);
    try {
      onQueued(await api.importRepository(r.repo));
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setBusy("remove");
    try {
      await api.removeSavedRepository(r.repo);
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
      setBusy(null);
    }
  }

  return (
    <li className="py-3">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="break-all text-[0.95rem] font-semibold text-ink">
            {r.repo}
            {r.unseen ? <span className="ml-2 align-middle text-[0.74rem] font-semibold text-accent">New changes</span> : null}
          </p>
          <p className="t-num mt-0.5 text-[0.78rem] text-ink-3">
            {pending
              ? `${STATUS[r.job!.status]} · ${r.job!.message}`
              : r.imported
                ? `Indexed ${r.ingested_at_iso ? fmtDay(r.ingested_at_iso) : ""} at ${r.indexed_sha?.slice(0, 7) ?? "?"}`
                : r.job?.status === "failed"
                  ? "Last import failed. Import again to retry."
                  : "Not indexed yet"}
            {r.imported && r.changes?.available ? ` · ${ahead ? `${ahead} new commit${ahead === 1 ? "" : "s"} on GitHub` : "up to date"}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {r.imported ? (
            <button type="button" className="btn btn-ghost btn-sm" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
              {open ? "Hide changes" : "What changed"}
            </button>
          ) : null}
          {!pending && (!r.imported || ahead > 0) ? (
            <button type="button" className="btn btn-line btn-sm" disabled={busy !== null} onClick={() => void reimport()}>
              {busy === "import" ? <LoaderCircle size={14} className="animate-spin motion-reduce:animate-none" aria-hidden /> : <RefreshCw size={14} aria-hidden />}
              {r.imported ? "Update import" : "Import"}
            </button>
          ) : null}
          {r.imported ? (
            selected ? (
              <span className="px-2 text-[0.8rem] font-semibold text-accent">Selected</span>
            ) : (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => onUse(r.repo)}>
                Use
              </button>
            )
          ) : null}
          <button type="button" className="btn btn-ghost btn-sm text-ink-3" disabled={busy !== null} onClick={() => void remove()} aria-label={`Remove ${r.repo} from your list`}>
            Remove
          </button>
        </div>
      </div>
      {error ? (
        <p role="alert" className="mt-1 text-[0.82rem] text-bad">
          {error}
        </p>
      ) : null}
      {open ? <Changes repo={r.repo} /> : null}
    </li>
  );
}

/** The signed-in person's own list: repositories they added or saved, with what changed on GitHub since import. */
export function SavedRepositories({
  selected,
  onUse,
  onQueued,
  revision,
}: {
  selected: string | null;
  onUse: (repo: string) => void;
  onQueued: (job: ImportJob) => void;
  revision: number;
}) {
  const saved = useResource(`my-repositories:${revision}`, (signal) => api.savedRepositories(signal));
  const reload = saved.reload;
  const pending = saved.data?.repositories.some((r) => r.job && (r.job.status === "queued" || r.job.status === "running"));
  useEffect(() => {
    if (!pending) return;
    const timer = window.setTimeout(reload, 10_000);
    return () => window.clearTimeout(timer);
  }, [pending, reload, saved.data]);

  return (
    <section aria-labelledby="saved-heading">
      <div className="sec-head">
        <h2 id="saved-heading">Your repositories</h2>
        <span className="sec-hint">Only you see this list</span>
      </div>
      {saved.loading && !saved.data ? (
        <SkeletonLines rows={2} />
      ) : saved.error ? (
        <ErrorState title="Could not load your repositories" error={saved.error} onRetry={reload} />
      ) : saved.data?.repositories.length ? (
        <ul className="divide-y divide-rule border-y border-rule">
          {saved.data.repositories.map((r) => (
            <SavedRow key={r.repo} r={r} selected={r.repo === selected} onUse={onUse} onQueued={onQueued} onChanged={reload} />
          ))}
        </ul>
      ) : (
        <p className="border-y border-rule py-3 text-[0.86rem] text-ink-2">
          Repositories you add or pick from GitHub are kept here, with the commits made since each import.
        </p>
      )}
    </section>
  );
}

function GitHubRow({ r, onQueued, onChanged }: { r: GitHubRepository; onQueued: (job: ImportJob) => void; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now] = useState(() => Date.now());
  const pending = r.job && (r.job.status === "queued" || r.job.status === "running");

  async function add() {
    setBusy(true);
    setError(null);
    try {
      if (r.imported) await api.saveRepository(r.full_name);
      else onQueued(await api.importRepository(r.full_name));
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2.5">
      <span className="min-w-0 flex-1">
        <a href={r.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 break-all text-[0.9rem] font-semibold text-ink hover:text-accent">
          {r.full_name}
          <ExternalLink size={12} className="shrink-0 text-ink-3" aria-hidden />
          <span className="sr-only">(opens GitHub in a new tab)</span>
        </a>
        {r.description ? <span className="block text-[0.8rem] text-ink-2">{r.description}</span> : null}
        <span className="t-num block text-[0.76rem] text-ink-3">
          {[r.language, r.stars ? `${r.stars.toLocaleString()} stars` : null, r.fork ? "fork" : null, r.archived ? "archived" : null,
            r.pushed_at ? `pushed ${fmtRelative(r.pushed_at, now)}` : null].filter(Boolean).join(" · ")}
        </span>
        {error ? (
          <span role="alert" className="block text-[0.8rem] text-bad">
            {error}
          </span>
        ) : null}
      </span>
      <span className="flex items-center gap-2">
        {pending ? (
          <span className="text-[0.8rem] font-semibold text-accent">{STATUS[r.job!.status]}</span>
        ) : r.saved ? (
          <span className="text-[0.8rem] text-ink-3">In your list</span>
        ) : (
          <button type="button" className="btn btn-line btn-sm" disabled={busy || r.size_kb > 100_000} onClick={() => void add()}
            title={r.size_kb > 100_000 ? "Larger than the 100 MB hosted limit" : undefined}>
            {busy ? <LoaderCircle size={14} className="animate-spin motion-reduce:animate-none" aria-hidden /> : null}
            {r.imported ? "Add to my list" : "Import"}
          </button>
        )}
      </span>
    </li>
  );
}

/** Public repositories from the connected GitHub account, or from any user or organization name. */
export function GitHubRepositoriesSection({ onQueued, onChanged }: { onQueued: (job: ImportJob) => void; onChanged: () => void }) {
  const id = useId();
  const providers = useResource("auth-providers", (signal) => api.authProviders(signal));
  const identity = useResource("github-identity", (signal) => api.githubIdentity(signal));
  const [owner, setOwner] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [filter, setFilter] = useState("");
  const [all, setAll] = useState(false);
  const github: GitHubIdentity | null = identity.data?.github ?? null;
  const active = owner ?? github?.login ?? null;
  const list = useResource(active ? `github-repos:${active.toLowerCase()}` : null, (signal) => api.githubRepositories(owner, signal));
  const reloadList = list.reload;

  const rows = useMemo(() => {
    const term = filter.trim().toLowerCase();
    const repos = list.data?.repositories ?? [];
    return term ? repos.filter((r) => r.full_name.toLowerCase().includes(term) || r.description.toLowerCase().includes(term)) : repos;
  }, [list.data, filter]);
  const shown = all ? rows : rows.slice(0, 12);

  return (
    <section aria-labelledby={`${id}-heading`}>
      <div className="sec-head">
        <h2 id={`${id}-heading`}>From GitHub</h2>
        {github ? (
          <span className="sec-hint">
            Connected as <span className="font-semibold text-ink-2">@{github.login}</span>
          </span>
        ) : null}
      </div>
      <div className="flex flex-col gap-3 border-t border-rule pt-3 sm:flex-row sm:items-end">
        {!github && providers.data?.github ? (
          <a href={connectHref()} className="btn btn-primary shrink-0">
            Connect GitHub
          </a>
        ) : null}
        <form
          className="flex flex-1 flex-col gap-1.5 sm:flex-row sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            const value = draft.trim().replace(/^https:\/\/github\.com\//, "").split("/")[0];
            if (value) {
              setOwner(value);
              setFilter("");
              setAll(false);
            }
          }}
        >
          <div className="flex-1">
            <label htmlFor={`${id}-owner`} className="text-[0.84rem] font-semibold text-ink">
              {github ? "Browse another user or organization" : "GitHub user or organization"}
            </label>
            <input id={`${id}-owner`} className="field mt-1.5 w-full" placeholder="e.g. vercel" value={draft} onChange={(e) => setDraft(e.target.value)}
              autoComplete="off" autoCapitalize="off" spellCheck={false} maxLength={100} />
          </div>
          <button type="submit" className="btn btn-line" disabled={!draft.trim()}>
            Show repositories
          </button>
          {owner && github ? (
            <button type="button" className="btn btn-ghost" onClick={() => { setOwner(null); setDraft(""); }}>
              Mine
            </button>
          ) : null}
        </form>
      </div>
      {!active ? (
        <p className="mt-3 text-[0.86rem] text-ink-2">
          {providers.data?.github
            ? "Connect GitHub to list your public repositories here and import any of them in one step."
            : "Enter a GitHub name to list its public repositories."}
        </p>
      ) : list.loading && !list.data ? (
        <div className="mt-3"><SkeletonLines rows={4} /></div>
      ) : list.error ? (
        <div className="mt-3"><ErrorState title="Could not load GitHub repositories" error={list.error} onRetry={reloadList} /></div>
      ) : list.data ? (
        <div className="mt-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="t-num text-[0.82rem] text-ink-3">
              {list.data.repositories.length} public repositor{list.data.repositories.length === 1 ? "y" : "ies"} from{" "}
              <span className="font-semibold text-ink-2">{list.data.owner}</span>
            </p>
            {list.data.repositories.length > 6 ? (
              <input className="field h-9 w-full sm:w-64" placeholder="Filter by name" aria-label="Filter repositories by name" value={filter} onChange={(e) => setFilter(e.target.value)} />
            ) : null}
          </div>
          {rows.length ? (
            <ul className="mt-2 divide-y divide-rule border-y border-rule">
              {shown.map((r) => (
                <GitHubRow key={r.full_name} r={r} onQueued={onQueued} onChanged={() => { reloadList(); onChanged(); }} />
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-[0.86rem] text-ink-2">No public repositories match.</p>
          )}
          {rows.length > shown.length ? (
            <button type="button" className="btn btn-ghost btn-sm mt-2" onClick={() => setAll(true)}>
              Show all {rows.length}
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
