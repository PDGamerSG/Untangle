"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Download, ExternalLink, GitBranch, GitCommitHorizontal, Network, Search } from "lucide-react";
import { api, API_BASE, errorMessage } from "@/lib/api";
import { useResource, useStoredValue } from "@/lib/hooks";
import { fmtDay, fmtDateTime } from "@/lib/format";
import { commitImpact, featureFiles, mapGraph, type MapCommit, type MapNode, type RepositoryMap } from "@/lib/repository-map";
import { useRepo } from "./RepoContext";
import { RepoSelect } from "./RepoSelect";
import { EmptyState, ErrorState, SkeletonLines } from "./states";
import { RepositoryGraph } from "./RepositoryGraph";
import { WaitStatus } from "./WaitStatus";

function BasicMapNotice({ repo }: { repo: string }) {
  const router = useRouter();
  const [, setTracked] = useStoredValue("untangle.import");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function refresh() {
    setBusy(true);
    setError(null);
    try {
      const job = await api.importRepository(repo);
      setTracked(job.id);
      router.push("/repositories");
    } catch (e) { setError(errorMessage(e)); setBusy(false); }
  }
  return <div className="card-muted space-y-2 p-4 text-[0.85rem]" role="status">
    <p className="font-semibold">File and commit map ready</p>
    <p>Explore directory groups, changed files and downloads below. Source import connections have not been indexed yet, so indirect impact is unknown.</p>
    <button type="button" className="btn btn-line btn-sm" onClick={refresh} disabled={busy}>{busy ? "Requesting…" : "Build import connections"}</button>
    <p className="text-ink-3">A repository refresh usually takes 3–20 minutes including the queue. Hosted size and history limits apply.</p>
    {error ? <p role="alert" className="text-bad">{error}</p> : null}
  </div>;
}

function Explorer({ data, offset, setOffset }: { data: RepositoryMap; offset: number; setOffset: (offset: number) => void }) {
  const [mode, setMode] = useState<"features" | "impact" | "history">("features");
  const [featureId, setFeatureId] = useState<string | null>(null);
  const [commitSha, setCommitSha] = useState<string | null>(null);
  const [selected, setSelected] = useState<MapNode | null>(null);
  const [query, setQuery] = useState("");
  const commit = data.commits.find(c => c.sha === commitSha) ?? null;
  const feature = data.features.find(f => f.id === featureId) ?? null;
  const impact = useMemo(() => commit ? commitImpact(data, commit) : null, [data, commit]);
  const graph = useMemo(() => mapGraph(data, featureId, mode === "features" ? null : commit, mode === "history"), [data, featureId, commit, mode]);
  const history = data.commits.filter(c => `${c.sha} ${c.title} ${c.author}`.toLowerCase().includes(query.toLowerCase().trim()));
  const source = `https://github.com/${data.repo}/blob/${data.head_sha ?? "HEAD"}/`;
  const fileUrl = (path: string) => `${source}${path.split("/").map(encodeURIComponent).join("/")}`;
  function chooseCommit(c: MapCommit) { setCommitSha(c.sha); setFeatureId(null); setSelected({ id: c.sha, name: c.sha.slice(0, 7), kind: "commit" }); setMode("impact"); }
  function chooseNode(node: MapNode) {
    setSelected(node);
    if (node.kind === "feature" && mode === "features") setFeatureId(node.id);
    if (node.kind === "commit") setCommitSha(node.id);
  }
  function overview() { setMode("features"); setFeatureId(null); setCommitSha(null); setSelected(null); }

  return <>
    {data.index_status === "basic" ? <BasicMapNotice repo={data.repo} /> : null}
    <dl className="stat-strip grid-cols-2 lg:grid-cols-4">
      <div><dt>Feature definitions</dt><dd>{data.features.length}</dd><p className="mt-1 text-[0.76rem] text-ink-3">{data.features.some(f => f.source === "manifest") ? "from repository manifest" : "inferred directory groups"}</p></div>
      <div><dt>Files in this map</dt><dd>{data.files.length}</dd><p className="mt-1 text-[0.76rem] text-ink-3">of {data.total_files} indexed paths</p></div>
      <div><dt>Import connections</dt><dd>{data.imports.length}</dd><p className="mt-1 text-[0.76rem] text-ink-3">at the indexed HEAD</p></div>
      <div><dt>Indexed commits</dt><dd>{data.total_commits}</dd><p className="mt-1 text-[0.76rem] text-ink-3">browse the history below</p></div>
    </dl>

    <section aria-label="Feature and commit explorer" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1" role="group" aria-label="Map view">
          <button type="button" className="filter-pill inline-flex items-center gap-2" aria-pressed={mode === "features"} onClick={overview}><Network size={15} />Feature connections</button>
          <button type="button" className="filter-pill inline-flex items-center gap-2" aria-pressed={mode === "history"} onClick={() => { setMode("history"); setSelected(null); }}><GitBranch size={15} />Commit history</button>
          {commit ? <button type="button" className="filter-pill" aria-pressed={mode === "impact"} onClick={() => setMode("impact")}>Impact of {commit.sha.slice(0, 7)}</button> : null}
        </div>
        <a className="btn btn-line btn-sm" href={`${API_BASE}/repository-map/obsidian?${new URLSearchParams({ repo: data.repo, offset: "0", limit: "200" })}`} download><Download size={14} />Export to Obsidian</a>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-[0.8rem] text-ink-2">
        <p>{mode === "history" ? "Arrows point from each commit to its parents. Ancestry does not imply feature dependency." : mode === "impact" ? "Red marks changed files and potentially affected features. Follow arrows to inspect dependency paths." : feature ? `Entry points and imports behind ${feature.name}.` : "Dashed connections mean features share code. Select a feature to trace its imports."}</p>
        {feature ? <button type="button" className="btn btn-ghost btn-sm" onClick={overview}>All features</button> : null}
      </div>
      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0"><RepositoryGraph key={`${mode}:${featureId}:${commitSha}`} nodes={graph.nodes} edges={graph.edges} selected={selected?.id ?? null} onSelect={chooseNode} />
          {graph.omitted ? <p className="mt-2 text-[0.76rem] text-ink-3">{graph.omitted} files omitted from the drawing to keep it readable; impact counts use the whole returned map.</p> : null}
        </div>
        <section aria-label="Graph inspector" className="card min-w-0 space-y-4 p-5">
          {commit && mode !== "features" ? <>
            <p className="eyebrow">Commit impact estimate</p>
            <h2 className="break-words text-[1rem] font-semibold">{commit.title}</h2>
            <a className="inline-flex items-center gap-1 text-[0.8rem] text-accent" href={`https://github.com/${data.repo}/commit/${commit.sha}`} target="_blank" rel="noreferrer">{commit.sha.slice(0, 12)} <ExternalLink size={12} /></a>
            <p className="text-[0.8rem] text-ink-3">{commit.author} · {fmtDay(commit.authored_at_iso)}</p>
            <div className="rounded-lg border border-warn/30 bg-warn/5 p-3 text-[0.8rem] leading-relaxed text-ink-2">No revert has been run. These paths indicate code to review and test; they do not prove a feature will break.{commit.is_merge ? " This is a merge commit; a real revert also needs a mainline parent." : ""}</div>
            {commit.is_merge && !commit.files.length ? <p className="text-[0.8rem] text-warn">The merge&apos;s parent-specific diff is not indexed. Its empty changed-file list must not be read as zero impact.</p> : null}
            {selected?.kind === "file" ? <div className="rounded-md border border-rule p-3"><p className="text-[0.8rem] font-semibold">Selected file</p><a className="mt-1 block break-all text-[0.78rem] text-accent" href={fileUrl(selected.id)} target="_blank" rel="noreferrer">{selected.id}</a></div> : null}
            <div><h3 className="text-[0.9rem] font-semibold">{impact?.features.length} potentially affected features</h3>
              <ul className="mt-2 space-y-3">{impact?.features.map(f => <li key={f.feature.id}><p className="text-[0.85rem] font-semibold text-bad">{f.feature.name}</p><p className="mt-1 break-words font-mono text-[0.72rem] leading-relaxed text-ink-2">{f.path.join(" → ")}</p></li>)}</ul>
              {!impact?.features.length ? <p className="mt-2 text-[0.8rem] text-ink-3">No path to a defined feature was found. This does not establish that reverting is safe.</p> : null}
            </div>
            <p className="text-[0.8rem] text-ink-3">{impact?.direct.length} changed files · {impact?.indirect.length} importing files{impact?.unindexed.length ? ` · ${impact.unindexed.length} paths absent at indexed HEAD` : ""}</p>
            <details className="text-[0.8rem]"><summary className="cursor-pointer font-semibold">Changed files</summary><ul className="mt-2 space-y-1">{commit.files.map(f => <li className="break-all" key={f.path}><span className="mr-2 font-mono text-ink-3">{f.change}</span>{f.path}</li>)}</ul></details>
            <div className="border-t border-rule pt-3 text-[0.78rem]"><p className="font-semibold">Git parents</p>{commit.parents.length ? <ul className="mt-1 space-y-1">{commit.parents.map(parent => <li key={parent}><a href={`https://github.com/${data.repo}/commit/${parent}`} className="text-accent" target="_blank" rel="noreferrer">{parent.slice(0, 12)}</a></li>)}</ul> : <p className="mt-1 text-ink-3">{commit.parents_known ? "Root commit" : "Parent metadata not indexed"}</p>}</div>
          </> : selected?.kind === "file" ? <>
            <p className="eyebrow">Source file</p><h2 className="break-all text-[0.95rem] font-semibold">{selected.id}</h2>
            <a href={fileUrl(selected.id)} target="_blank" rel="noreferrer" className="btn btn-line btn-sm">Open indexed source <ExternalLink size={13} /></a>
            <p className="text-[0.8rem] text-ink-3">Observed imports from this file:</p>
            <ul className="space-y-2">{data.imports.filter(e => e.source === selected.id).map(e => <li key={e.target} className="break-all text-[0.78rem]"><button type="button" className="text-left text-accent hover:underline" onClick={() => setSelected({ id: e.target, name: e.target, kind: "file" })}>{e.target}</button><span className="block text-ink-3">line {e.line} · {e.specifier}</span></li>)}</ul>
          </> : feature ? <>
            <p className="eyebrow">{feature.source === "manifest" ? "Defined feature" : "Inferred code area"}</p><h2 className="text-[1.15rem] font-semibold">{feature.name}</h2><p className="text-[0.85rem] leading-relaxed text-ink-2">{feature.description}</p>
            <p className="text-[0.8rem] text-ink-3">{featureFiles(data, feature).size} reachable files in the current import graph.</p>
            <h3 className="text-[0.85rem] font-semibold">Entry points</h3><ul className="space-y-2">{feature.entrypoints.map(p => <li key={p}><a href={fileUrl(p)} className="break-all text-[0.78rem] text-accent hover:underline" target="_blank" rel="noreferrer">{p}</a></li>)}</ul>
          </> : <>
            <Network className="text-accent" size={28} /><h2 className="text-[1.1rem] font-semibold">Follow a feature through the code.</h2>
            <p className="text-[0.85rem] leading-relaxed text-ink-2">Select a feature to inspect its entry points and dependencies. Choose a commit below to see the potential reach of its changes.</p>
            <div className="space-y-2 border-t border-rule pt-4">{data.features.map(f => <button key={f.id} type="button" className="block w-full rounded-md p-2 text-left text-[0.85rem] text-accent hover:bg-accent-soft" onClick={() => { setFeatureId(f.id); setSelected({ id: f.id, name: f.name, kind: "feature" }); setMode("features"); }}>{f.name}</button>)}</div>
          </>}
        </section>
      </div>
    </section>

    <section aria-label="Repository commits" className="space-y-3">
      <div className="sec-head"><div><h2>Every change has a trail</h2><p className="mt-1 text-[0.8rem] text-ink-3">Select a commit to trace its potential impact. Showing {data.commits.length ? offset + 1 : 0}–{offset + data.commits.length} of {data.total_commits} indexed commits.</p></div>
        <div className="relative w-full sm:w-72"><label className="sr-only" htmlFor="commit-filter">Filter loaded commits</label><Search size={15} className="absolute left-3 top-3 text-ink-3" /><input id="commit-filter" className="field pl-9" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Find a message or SHA on this page" /></div>
      </div>
      <div className="card max-h-80 overflow-y-auto"><ul className="divide-y divide-rule">{history.map(c => <li key={c.sha}><button type="button" className="flex w-full items-start gap-3 p-4 text-left hover:bg-accent-soft" aria-label={`Inspect commit ${c.sha.slice(0, 7)}`} aria-pressed={commitSha === c.sha} onClick={() => chooseCommit(c)}><GitCommitHorizontal size={20} className="mt-0.5 shrink-0 text-accent" /><span className="min-w-0 flex-1"><span className="block break-words text-[0.88rem] font-semibold">{c.title}</span><span className="mt-1 block text-[0.76rem] text-ink-3">{c.sha.slice(0, 7)} · {c.author} · {fmtDay(c.authored_at_iso)} · {c.files.length} files{c.is_merge ? " · merge" : ""}</span></span></button></li>)}</ul>{!history.length ? <p className="p-5 text-[0.85rem] text-ink-3">No commits match on this page.</p> : null}</div>
      <div className="flex justify-between"><button type="button" className="btn btn-line btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 40))}>Newer commits</button><button type="button" className="btn btn-line btn-sm" disabled={!data.has_more} onClick={() => setOffset(offset + 40)}>Older commits</button></div>
    </section>
    <details className="card p-4 text-[0.8rem] leading-relaxed text-ink-2"><summary className="cursor-pointer font-semibold">What this graph can establish</summary><div className="mt-3 space-y-2"><p>Indexed {fmtDateTime(data.indexed_at_iso)} at {data.head_sha?.slice(0, 12)}. {data.coverage.scanned_files ?? 0} Python/JS/TS files scanned; {data.coverage.unresolved_local_imports ?? 0} unresolved local JS/TS imports; {data.coverage.parse_failures ?? 0} parse failures.</p><p>Imports reflect this indexed HEAD, not the version before each commit. Runtime calls, computed imports, configuration effects and unsupported languages can add relationships this graph cannot see. Actual breakage requires a baseline and a tested revert in an isolated checkout. Obsidian exports contain this map and up to 200 recent indexed commits; older history is available through the paginated API.</p>{data.warnings.map((w, i) => <p key={i} className="text-warn">{w}</p>)}</div></details>
  </>;
}

function RepositoryMapBody({ repo }: { repo: string }) {
  const [offset, setOffset] = useState(0);
  const resource = useResource(`repository-map:${repo}:${offset}`, signal => api.repositoryMap(repo, offset, signal));
  if (resource.error) return <ErrorState title="Could not load the repository map" error={resource.error} onRetry={resource.reload} />;
  if (!resource.data) return <div className="space-y-4"><WaitStatus label="Loading files, features and commit history." min={1} max={5} /><div className="card p-6" aria-label="Loading repository map"><SkeletonLines rows={8} /></div></div>;
  if (!resource.data.files.length && !resource.data.commits.length) return <EmptyState title="No files or commits have been indexed yet.">Open Repositories to check this repository&apos;s import status and retry an interrupted import.</EmptyState>;
  return <Explorer key={`${repo}:${offset}:${resource.data.head_sha}`} data={resource.data} offset={offset} setOffset={setOffset} />;
}

export function RepositoryMapPage() {
  const { repo } = useRepo();
  return <div className="space-y-7"><header className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow mb-2">Repository map</p><h1 className="t-display text-[2.1rem] leading-tight sm:text-[2.5rem]">How the repository fits together.</h1><p className="mt-2 max-w-2xl text-[0.95rem] leading-relaxed text-ink-2">Trace features through their code and commit history. Explore what a change could affect before deciding what to test.</p></div><RepoSelect compact /></header>{repo ? <RepositoryMapBody key={repo} repo={repo} /> : <EmptyState title="Choose an ingested repository to explore its map." />}</div>;
}
