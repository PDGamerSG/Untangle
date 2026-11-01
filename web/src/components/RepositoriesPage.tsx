"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { ArrowUpRight, CheckCircle2, Circle, CircleAlert, ExternalLink, LoaderCircle, Plus, RefreshCw, X } from "lucide-react";
import { useRepo } from "./RepoContext";
import { RepositoryOverviewPanel } from "./RepositoryOverview";
import { EmptyState, ErrorState, SkeletonLines } from "./states";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useResource, useStoredValue } from "@/lib/hooks";
import { fmtDateTime, fmtDay, fmtRelative } from "@/lib/format";
import type { ImportJob, ImportStatus, RepositoryImports, RepoSummary } from "@/lib/types";

const JOB_KEY = "untangle.import";
const POLL_MS = 7000;
/** After a failed poll (network, 5xx), wait longer before asking again. */
const POLL_BACKOFF_MS = 15000;

/** Validate after removing GitHub's optional clone suffix and trailing slash. */
const REPO_PATTERN = /^(?:https:\/\/github\.com\/)?[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\/[A-Za-z0-9._-]{1,100}$/;

const STAGES = [
  { key: "git", label: "Git history" },
  { key: "github", label: "Pull requests and issues" },
  { key: "head", label: "Current code" },
  { key: "history", label: "Changes over time" },
  { key: "decisions", label: "Decisions" },
  { key: "embeddings", label: "Search index" },
  { key: "write", label: "Save to graph" },
] as const;

const STATUS_TEXT: Record<ImportStatus, string> = { queued: "Queued", running: "Indexing", complete: "Indexed", failed: "Failed" };

const pending = (s: ImportStatus) => s === "queued" || s === "running";

/** The API sends progress as an integer from 0 to 100; clamp it so a stray value cannot overflow the bar. */
function percent(p: number): number {
  return Math.max(0, Math.min(100, Math.round(p)));
}

function humanise(key: string) {
  const s = key.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function StatusBadge({ status }: { status: ImportStatus }) {
  const tone =
    status === "complete"
      ? "border-ok/30 bg-ok/10 text-ok"
      : status === "failed"
        ? "border-bad/30 bg-bad-soft text-bad"
        : "border-accent/30 bg-accent-soft text-accent";
  const Icon = status === "complete" ? CheckCircle2 : status === "failed" ? CircleAlert : status === "running" ? LoaderCircle : Circle;
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[0.74rem] font-semibold ${tone}`}>
      <Icon size={12} className={status === "running" ? "animate-spin motion-reduce:animate-none" : undefined} aria-hidden />
      {STATUS_TEXT[status]}
    </span>
  );
}

function Stages({ job }: { job: ImportJob }) {
  const at = STAGES.findIndex((s) => s.key === job.stage);
  return (
    <ol className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-7" aria-label="Indexing stages">
      {STAGES.map((s, i) => {
        const state = job.status === "complete" || (at >= 0 && i < at) ? "done" : at === i && pending(job.status) ? "current" : "todo";
        return (
          <li
            key={s.key}
            aria-current={state === "current" ? "step" : undefined}
            className={`flex items-center gap-1.5 rounded-md border px-2 py-1.5 text-[0.76rem] leading-tight ${
              state === "done"
                ? "border-transparent bg-surface-2 text-ink-2"
                : state === "current"
                  ? "border-accent/40 bg-accent-soft font-semibold text-accent"
                  : "border-rule text-ink-3"
            }`}
          >
            {state === "done" ? (
              <CheckCircle2 size={13} className="shrink-0 text-ok" aria-hidden />
            ) : state === "current" ? (
              <LoaderCircle size={13} className="shrink-0 animate-spin motion-reduce:animate-none" aria-hidden />
            ) : (
              <Circle size={13} className="shrink-0" aria-hidden />
            )}
            <span>{s.label}</span>
            <span className="sr-only">{state === "done" ? "(done)" : state === "current" ? "(in progress)" : "(not started)"}</span>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * Follows one import job until it finishes, polling every few seconds. The job id is kept in local storage by the
 * parent, so a reload picks the same job up again. When this session watches a job go from pending to complete, the
 * new repository becomes the selected one.
 */
function JobTracker({
  id,
  initial,
  imports,
  onDismiss,
  onRetried,
}: {
  id: string;
  initial: ImportJob | null;
  imports: RepositoryImports | undefined;
  onDismiss: () => void;
  onRetried: (job: ImportJob) => void;
}) {
  const { setRepo, reload, repos } = useRepo();
  const router = useRouter();
  const [job, setJob] = useState<ImportJob | null>(initial);
  const [pollError, setPollError] = useState<string | null>(null);
  const [gone, setGone] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [selected, setSelected] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  /** Bumped by a retry that reuses this job id, to start polling again. */
  const [generation, setGeneration] = useState(0);
  const lastStatus = useRef<ImportStatus | null>(initial?.status ?? null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    const tick = () => {
      api.repositoryImport(id, controller.signal).then(
        (next) => {
          if (cancelled) return;
          const before = lastStatus.current;
          lastStatus.current = next.status;
          setJob(next);
          setPollError(null);
          setNow(Date.now());
          if (before && pending(before) && next.status === "complete") {
            setRepo(next.repo);
            reload();
            setSelected(true);
          }
          if (pending(next.status)) timer = setTimeout(tick, POLL_MS);
        },
        (e: unknown) => {
          if (cancelled || (e instanceof DOMException && e.name === "AbortError")) return;
          if (e instanceof ApiError && e.status === 404) {
            setGone(true);
            return;
          }
          setPollError(errorMessage(e));
          timer = setTimeout(tick, POLL_BACKOFF_MS);
        },
      );
    };
    tick();
    return () => {
      cancelled = true;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [id, generation, setRepo, reload]);

  const retry = async () => {
    if (!job) return;
    setRetrying(true);
    setRetryError(null);
    try {
      const next = await api.importRepository(job.repo);
      lastStatus.current = next.status;
      setJob(next);
      setGeneration((g) => g + 1);
      onRetried(next);
    } catch (e) {
      setRetryError(errorMessage(e));
    } finally {
      setRetrying(false);
    }
  };

  if (gone)
    return (
      <div className="card-muted flex flex-wrap items-center justify-between gap-3 p-4" role="status">
        <p className="text-[0.88rem] text-ink-2">The import you were following is no longer on record.</p>
        <button type="button" className="btn btn-line btn-sm" onClick={onDismiss}>
          Dismiss
        </button>
      </div>
    );
  if (!job)
    return (
      <div className="card p-5">
        {pollError ? <ErrorState title="Could not check the import" error={pollError} /> : <SkeletonLines rows={3} />}
      </div>
    );

  const indexed = repos?.some((r) => r.full_name === job.repo);
  const worker = imports?.worker;
  return (
    <section aria-labelledby="job-heading" className="card overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-rule p-4 sm:p-5">
        <div className="min-w-0">
          <p className="eyebrow">Import</p>
          <h2 id="job-heading" className="mt-1 break-all text-[1.1rem] font-semibold text-ink">
            {job.repo}
          </h2>
          <p className="t-num mt-0.5 text-[0.78rem] text-ink-3">
            Requested {fmtDateTime(job.created_at_iso)} · updated {fmtRelative(job.updated_at_iso, now)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={job.status} />
          {!pending(job.status) ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={onDismiss} aria-label="Dismiss this import">
              <X size={15} aria-hidden />
            </button>
          ) : null}
        </div>
      </div>

      <div className="space-y-4 p-4 sm:p-5">
        <div aria-live="polite" className="space-y-2">
          <p className="text-[0.92rem] text-ink">{job.message || STATUS_TEXT[job.status]}</p>
          {job.status === "queued" ? (
            <p className="text-[0.84rem] leading-relaxed text-ink-2">
              Waiting for the indexing worker, which usually picks jobs up within a few minutes. You can leave this page; the import keeps going
              and this page finds it again when you return.
              {worker?.scheduling ? <> Schedule: {worker.scheduling}.</> : null}
            </p>
          ) : null}
          {job.status === "running" ? (
            <p className="text-[0.84rem] leading-relaxed text-ink-2">
              Large histories take longer. You can leave this page; the import keeps going and this page finds it again when you return.
            </p>
          ) : null}
          {pending(job.status) ? <p className="text-[0.84rem] text-ink-2">
            {job.estimate?.overdue ? "Taking longer than estimated. The worker has not reported completion; status will keep updating." :
              job.estimate?.remaining_max_seconds != null ? `Estimated time remaining: ${Math.max(1, Math.ceil(job.estimate.remaining_min_seconds / 60))}–${Math.max(1, Math.ceil(job.estimate.remaining_max_seconds / 60))} minutes.` :
                "Estimated time remaining: 3–20 minutes, including the worker queue."}
            {job.estimate ? ` ${Math.floor(job.estimate.elapsed_seconds / 60)}m ${job.estimate.elapsed_seconds % 60}s elapsed.` : ""}
            {" "}Estimates vary with repository size, queue delays and GitHub availability.
          </p> : null}
        </div>

        {job.status !== "failed" ? (
          <div>
            <div className="flex items-center justify-between text-[0.78rem] text-ink-3">
              <span>Progress</span>
              <span className="t-num">{percent(job.progress)}%</span>
            </div>
            <div
              role="progressbar"
              aria-label={`Indexing ${job.repo}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={percent(job.progress)}
              className="mt-1 h-2 overflow-hidden rounded-full bg-surface-3"
            >
              <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${percent(job.progress)}%` }} />
            </div>
          </div>
        ) : null}

        <Stages job={job} />

        {pollError ? (
          <p className="text-[0.82rem] text-warn" role="status">
            Could not check for updates ({pollError}). Trying again shortly.
          </p>
        ) : null}

        {job.status === "failed" ? (
          <div className="space-y-3">
            <ErrorState title="The import did not finish" error={job.error ?? job.message ?? "No reason was recorded."} />
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" className="btn btn-primary btn-sm" onClick={retry} disabled={retrying}>
                <RefreshCw size={14} className={retrying ? "animate-spin motion-reduce:animate-none" : undefined} aria-hidden />
                {retrying ? "Requesting…" : "Try again"}
              </button>
              {retryError ? (
                <p role="alert" className="text-[0.84rem] text-bad">
                  {retryError}
                </p>
              ) : null}
            </div>
          </div>
        ) : null}

        {job.status === "complete" ? (
          <div className="space-y-3">
            {selected ? (
              <p className="flex items-center gap-2 text-[0.9rem] font-semibold text-ok" role="status">
                <CheckCircle2 size={16} aria-hidden /> {job.repo} is indexed and now selected across Untangle.
              </p>
            ) : null}
            {job.summary && Object.keys(job.summary).length ? (
              <dl className="stat-strip grid-cols-2 sm:grid-cols-4" aria-label="Import summary">
                {Object.entries(job.summary).map(([k, v]) => (
                  <div key={k}>
                    <dt>{humanise(k)}</dt>
                    <dd className="t-num break-words text-[1.1rem]">{typeof v === "number" ? v.toLocaleString() : v}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {indexed ? (
                <>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => {
                      setRepo(job.repo);
                      router.push("/dashboard");
                    }}
                  >
                    Open {job.repo} <ArrowUpRight size={14} aria-hidden />
                  </button>
                  <button
                    type="button"
                    className="btn btn-line btn-sm"
                    onClick={() => {
                      setRepo(job.repo);
                      router.push("/ask");
                    }}
                  >
                    Ask a question
                  </button>
                </>
              ) : (
                <button type="button" className="btn btn-line btn-sm" onClick={reload}>
                  <RefreshCw size={14} aria-hidden /> Refresh the repository list
                </button>
              )}
            </div>
          </div>
        ) : null}

        {job.warnings.length ? (
          <ul className="space-y-1 rounded-lg bg-surface-2 p-3" aria-label="Import warnings">
            {job.warnings.map((w) => (
              <li key={w} className="flex gap-2 text-[0.82rem] leading-relaxed text-ink-2">
                <CircleAlert size={14} className="mt-0.5 shrink-0 text-warn" aria-hidden />
                {w}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  );
}

function Limits({ imports }: { imports: RepositoryImports }) {
  const l = imports.limits;
  const mb = l.max_repository_size_kb / 1024;
  return (
    <ul className="mt-3 grid gap-x-6 gap-y-1 text-[0.8rem] leading-relaxed text-ink-3 sm:grid-cols-2">
      <li>Public GitHub repositories up to {mb >= 1 ? `${Math.round(mb).toLocaleString()} MB` : `${l.max_repository_size_kb} KB`}.</li>
      <li>
        Reads up to {l.max_commits.toLocaleString()} commits, {l.max_prs.toLocaleString()} pull requests and {l.max_issues.toLocaleString()} issues.
      </li>
      <li>{l.imports_per_day.toLocaleString()} new imports a day, shared by everyone using this deployment.</li>
      <li>Imported repositories are visible to everyone using this deployment.</li>
    </ul>
  );
}

function AddRepository({
  imports,
  onQueued,
}: {
  imports: ReturnType<typeof useResource<RepositoryImports>>;
  onQueued: (job: ImportJob) => void;
}) {
  const id = useId();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const disabled = imports.data?.enabled === false;

  const submit = async () => {
    const repository = value.trim().replace(/\/+$/, "").replace(/\.git$/, "").replace(/^https:\/\/github\.com\//, "");
    if (!REPO_PATTERN.test(repository) || [".", ".."].includes(repository.split("/").at(-1) ?? "")) {
      setError("Enter a GitHub repository as owner/name, or as the full https://github.com/owner/name link.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const job = await api.importRepository(repository);
      setValue("");
      onQueued(job);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby={`${id}-heading`} className="card p-4 sm:p-5">
      <h2 id={`${id}-heading`} className="text-[1.05rem] font-semibold text-ink">
        Add a public GitHub repository
      </h2>
      <p className="mt-1 max-w-2xl text-[0.86rem] leading-relaxed text-ink-2">
        Untangle reads its commits, pull requests, issues, docs and code, then records the decisions it finds. Once indexed, every tool here
        works on it. No sign-in or token is needed.
      </p>
      <form
        className="mt-4"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <label htmlFor={id} className="text-[0.84rem] font-semibold text-ink">
          GitHub repository
        </label>
        <div className="mt-1.5 flex flex-col gap-2 sm:flex-row">
          <input
            id={id}
            className="field flex-1"
            placeholder="owner/name or https://github.com/owner/name"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (error) setError(null);
            }}
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            inputMode="url"
            disabled={disabled}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${id}-error` : undefined}
          />
          <button type="submit" className="btn btn-primary" disabled={busy || disabled || !value.trim()}>
            {busy ? <LoaderCircle size={16} className="animate-spin motion-reduce:animate-none" aria-hidden /> : <Plus size={16} aria-hidden />}
            {busy ? "Adding…" : "Add repository"}
          </button>
        </div>
        {error ? (
          <p id={`${id}-error`} role="alert" className="mt-2 text-[0.85rem] text-bad">
            {error}
          </p>
        ) : null}
      </form>
      {imports.loading ? (
        <div className="mt-3 h-4 w-2/3 skeleton" aria-hidden />
      ) : imports.error ? (
        <p className="mt-3 text-[0.82rem] text-ink-3">
          Import limits are unavailable right now ({imports.error}).{" "}
          <button type="button" className="font-semibold underline underline-offset-4" onClick={imports.reload}>
            Retry
          </button>
        </p>
      ) : imports.data ? (
        disabled ? (
          <p className="mt-3 text-[0.85rem] text-warn">Adding repositories is turned off on this deployment.</p>
        ) : (
          <Limits imports={imports.data} />
        )
      ) : null}
    </section>
  );
}

function RecentImports({ jobs, tracked, onTrack }: { jobs: ImportJob[]; tracked: string | null; onTrack: (job: ImportJob) => void }) {
  const [now] = useState(() => Date.now());
  const rows = jobs.filter((j) => j.id !== tracked).slice(0, 8);
  if (!rows.length) return null;
  return (
    <section aria-labelledby="recent-imports-heading">
      <div className="sec-head">
        <h2 id="recent-imports-heading">Recent imports</h2>
        <span className="sec-hint">Shared by everyone on this deployment</span>
      </div>
      <ul className="divide-y divide-rule border-y border-rule">
        {rows.map((j) => (
          <li key={j.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2.5">
            <span className="min-w-0">
              <span className="block break-all text-[0.9rem] font-semibold text-ink">{j.repo}</span>
              <span className="t-num block text-[0.76rem] text-ink-3">
                {j.status === "failed" && j.error ? j.error : j.message} · {fmtRelative(j.updated_at_iso, now)}
              </span>
            </span>
            <span className="flex items-center gap-2">
              <StatusBadge status={j.status} />
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => onTrack(j)} aria-label={`Show details for ${j.repo}`}>
                Details
              </button>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function RepoCard({ r, selected, onSelect }: { r: RepoSummary; selected: boolean; onSelect: () => void }) {
  return (
    <li className={`card flex min-w-0 flex-col gap-3 p-4 ${selected ? "border-accent/50 ring-1 ring-accent/30" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-all text-[0.98rem] font-semibold text-ink">{r.full_name}</p>
          <p className="t-num mt-0.5 text-[0.76rem] text-ink-3">
            {r.head_sha ? (
              <>
                Indexed {r.ingested_at_iso ? `${fmtDay(r.ingested_at_iso)} ` : ""}at <code className="t-code">{r.head_sha.slice(0, 7)}</code>
              </>
            ) : (
              "Git history not indexed"
            )}
          </p>
        </div>
        {r.url && /^https?:\/\//.test(r.url) ? (
          <a href={r.url} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm -mr-2 -mt-1 shrink-0" aria-label={`${r.full_name} on GitHub (opens in a new tab)`}>
            <ExternalLink size={14} aria-hidden />
          </a>
        ) : null}
      </div>
      <dl className="t-num grid grid-cols-3 gap-2 text-[0.76rem] text-ink-3">
        {(
          [
            ["Decisions", r.counts.decisions],
            ["Commits", r.counts.commits],
            ["PRs", r.counts.prs],
            ["Issues", r.counts.issues],
            ["Calls", r.counts.meetings],
          ] as const
        ).map(([label, n]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd className="text-[0.92rem] font-semibold text-ink">{n.toLocaleString()}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-auto">
        {selected ? (
          <span className="inline-flex items-center gap-1.5 text-[0.82rem] font-semibold text-accent">
            <CheckCircle2 size={15} aria-hidden /> Selected
          </span>
        ) : (
          <button type="button" className="btn btn-line btn-sm" onClick={onSelect} aria-label={`Use ${r.full_name}`}>
            Use this repository
          </button>
        )}
      </div>
    </li>
  );
}

export function RepositoriesPage() {
  const { repos, repo, setRepo, loading, error, reload } = useRepo();
  const imports = useResource("repository-imports", (signal) => api.repositoryImports(signal));
  const [tracked, setTracked] = useStoredValue(JOB_KEY);
  const [initial, setInitial] = useState<ImportJob | null>(null);
  const reloadImports = imports.reload;

  const follow = (job: ImportJob) => {
    setInitial(job);
    setTracked(job.id);
    reloadImports();
  };

  return (
    <div className="space-y-10">
      <header className="max-w-3xl">
        <h1 className="t-display text-[2.2rem] leading-[1.04] text-ink sm:text-[2.8rem]">Repositories</h1>
        <p className="mt-2 text-[0.98rem] leading-relaxed text-ink-2">
          Add a repository, follow its import, and choose which one every page reads from. Counts and lists below come from what was indexed.
        </p>
      </header>

      <AddRepository imports={imports} onQueued={follow} />

      {tracked ? (
        <JobTracker
          key={tracked}
          id={tracked}
          initial={initial?.id === tracked ? initial : (imports.data?.jobs.find((j) => j.id === tracked) ?? null)}
          imports={imports.data}
          onDismiss={() => {
            setTracked(null);
            setInitial(null);
            reloadImports();
          }}
          onRetried={follow}
        />
      ) : null}

      {imports.data ? <RecentImports jobs={imports.data.jobs} tracked={tracked} onTrack={follow} /> : null}

      <section aria-labelledby="indexed-heading">
        <div className="sec-head">
          <h2 id="indexed-heading">Indexed repositories</h2>
          {repos?.length ? <span className="sec-hint t-num">{repos.length.toLocaleString()} available</span> : null}
        </div>
        {loading ? (
          <SkeletonLines rows={3} />
        ) : error ? (
          <ErrorState title="Could not load repositories" error={error} onRetry={reload} />
        ) : repos?.length ? (
          <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {repos.map((r) => (
              <RepoCard key={r.full_name} r={r} selected={r.full_name === repo} onSelect={() => setRepo(r.full_name)} />
            ))}
          </ul>
        ) : (
          <EmptyState title="No repository has been indexed yet">Add one above to get started.</EmptyState>
        )}
      </section>

      {repo ? (
        <section aria-labelledby="inventory-heading" className="space-y-4 border-t border-rule pt-8">
          <div>
            <p className="eyebrow">Selected repository</p>
            <h2 id="inventory-heading" className="t-display mt-1 break-all text-[1.7rem] text-ink">
              {repo}
            </h2>
          </div>
          <RepositoryOverviewPanel key={repo} repo={repo} />
        </section>
      ) : null}

      <p className="text-[0.82rem] text-ink-3">
        Prefer the command line? <code className="t-code">uv run untangle ingest owner/name</code> indexes a repository into your own graph.{" "}
        <Link href="/dashboard" className="font-semibold text-ink-2 underline underline-offset-4">
          Back to the dashboard
        </Link>
      </p>
    </div>
  );
}
