"use client";

import Link from "next/link";
import { ArrowUpRight, ChevronDown, ExternalLink } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { RepoSelect } from "@/components/repositories/RepoSelect";
import { useRepo } from "@/components/repositories/RepoContext";
import { NoRepository } from "@/components/repositories/NoRepository";
import { CypherList } from "@/components/ask/WhyPanel";
import { ErrorState, SkeletonLines } from "@/components/ui/states";
import { ExportBrief } from "@/components/ui/ExportBrief";
import { WaitStatus } from "@/components/ui/WaitStatus";
import { api, errorMessage, externalHref } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDay } from "@/lib/format";
import { preflightExamples, preflightMarkdown, splitPaths } from "@/lib/preflight";
import type { PreflightResponse, PreflightTarget } from "@/lib/types";
import { InlineCode } from "@/components/ask/AnswerText";

const LEVEL_TEXT: Record<PreflightResponse["review"]["level"], string> = {
  high: "Review closely before merging",
  medium: "Worth a careful look",
  low: "Nothing recorded argues against it",
};
const LEVEL_CLASS: Record<PreflightResponse["review"]["level"], string> = { high: "text-bad", medium: "text-warn", low: "text-ok" };

const CHANGE_LABEL: Record<PreflightTarget["change"], string> = {
  edit: "edited", add: "added", remove: "removed", delete: "deleted", file: "named", mention: "described",
};

function TargetRow({ t }: { t: PreflightTarget }) {
  const name = t.key ?? t.name ?? t.path ?? t.id;
  return (
    <li className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-2.5 text-[0.88rem]">
      <span className="text-[0.75rem] font-semibold uppercase tracking-wide text-ink-3">{t.label === "ConfigKey" ? "Config" : t.label}</span>
      <Link href={`/entities/${encodeURIComponent(t.id)}`} className="t-code break-all text-ink underline-offset-4 hover:underline">{name}</Link>
      {t.path && t.label !== "File" ? <span className="t-code text-[0.8rem] text-ink-3">{t.path}</span> : null}
      <span className="text-ink-3">{CHANGE_LABEL[t.change]}</span>
      {t.current || t.proposed ? (
        <span className="t-code text-[0.82rem] text-ink-2">
          {t.current ?? "not set"}
          {t.proposed ? <> → <span className="font-semibold text-ink">{t.proposed}</span></> : null}
        </span>
      ) : null}
      {t.note ? <span className="basis-full text-[0.8rem] text-ink-3">{t.note}</span> : null}
    </li>
  );
}

function PathChain({ via }: { via: string[] }) {
  return (
    <span className="t-code break-all text-[0.84rem]">
      {via.map((p, i) => (
        <span key={`${p}-${i}`}>
          {i ? <span className="px-1 text-ink-3" aria-label="imports">→</span> : null}
          <span className={i === via.length - 1 ? "text-ink-3" : "text-ink"}>{p}</span>
        </span>
      ))}
    </span>
  );
}

function Result({ res, change }: { res: PreflightResponse; change: string }) {
  const { review, reach } = res;
  const hops = [1, 2, 3].map((h) => reach.reached.filter((r) => r.hop === h)).filter((g) => g.length);
  return (
    <div className="space-y-8">
      <section aria-labelledby="review-heading" className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="review-heading" className="text-[0.85rem] font-semibold text-ink-3">Review level</h2>
            <p className={`t-display mt-0.5 text-[1.9rem] leading-tight ${LEVEL_CLASS[review.level]}`}>
              {review.level[0].toUpperCase() + review.level.slice(1)}
              <span className="t-num ml-2 text-[1rem] text-ink-3">{review.score} of 100</span>
            </p>
            <p className="mt-1 text-[0.92rem] text-ink-2">{LEVEL_TEXT[review.level]}</p>
          </div>
          <ExportBrief label="Download for the pull request" filename={`untangle-preflight-${res.repo.replace("/", "-")}.md`} build={(origin) => preflightMarkdown(res, change, origin)} />
        </div>
        {review.reasons.length ? (
          <ul className="mt-4 divide-y divide-rule border-t border-rule" aria-label="Reasons for the review level">
            {review.reasons.map((r) => (
              <li key={r.text} className="flex gap-3 py-2 text-[0.9rem]">
                <span className="t-num w-10 shrink-0 text-right font-semibold text-ink-2">+{r.points}</span>
                <span className="text-ink"><InlineCode text={r.text} /></span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      {res.revivals.length ? (
        <section aria-labelledby="revivals-heading">
          <div className="sec-head"><h2 id="revivals-heading">Brings back a replaced value</h2></div>
          <ul className="card divide-y divide-rule">
            {res.revivals.map((r) => (
              <li key={`${r.target}-${r.replaced.id}`} className="space-y-1.5 px-4 py-3.5">
                <p className="text-[0.95rem] text-ink">
                  <span className="t-code font-semibold">{r.target}</span> {r.proposed === "added again" ? "is added back" : <>set to <span className="t-code font-semibold">{r.proposed}</span></>}
                </p>
                <p className="text-[0.88rem] text-ink-2">
                  That was the value until {fmtDay(r.replaced_by.valid_from_iso)}, when{" "}
                  <Link href={`/decisions/${encodeURIComponent(r.replaced_by.id)}`} className="text-ink underline underline-offset-4"><InlineCode text={r.replaced_by.text} /></Link>.
                </p>
                {r.reason ? <p className="border-l-2 border-rule-strong pl-3 text-[0.88rem] italic text-ink-2">{r.reason}</p> : null}
                {r.evidence && externalHref(r.evidence.url) ? (
                  <a href={externalHref(r.evidence.url)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[0.82rem] font-semibold text-accent underline-offset-4 hover:underline">
                    {r.evidence.title} <ExternalLink size={12} aria-hidden />
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {res.advisories.introduced.length || !res.advisories.checked || res.advisories.fixed.length ? (
        <section aria-labelledby="advisories-heading">
          <div className="sec-head"><h2 id="advisories-heading">Public advisories</h2><span className="sec-hint">from OSV.dev</span></div>
          {res.advisories.introduced.length ? (
            <ul className="card divide-y divide-rule">
              {res.advisories.introduced.map((a) => (
                <li key={`${a.package}-${a.advisory.id}`} className="px-4 py-3 text-[0.9rem]">
                  <p className="text-ink">
                    <span className="t-code font-semibold">{a.package}@{a.version}</span> is affected by{" "}
                    <a href={externalHref(a.advisory.url) ?? "#"} target="_blank" rel="noreferrer" className="font-semibold text-accent underline-offset-4 hover:underline">{a.advisory.id}</a>
                    {a.advisory.aliases[0] ? <span className="text-ink-3"> ({a.advisory.aliases[0]})</span> : null}; the current {a.current ?? "version"} is not.
                  </p>
                  {a.advisory.summary ? <p className="mt-0.5 text-[0.86rem] text-ink-2">{a.advisory.summary}</p> : null}
                  {!a.exact ? <p className="mt-0.5 text-[0.78rem] text-ink-3">Checked at the lowest version the range allows.</p> : null}
                </li>
              ))}
            </ul>
          ) : null}
          {res.advisories.fixed.length ? (
            <p className="mt-2 text-[0.86rem] text-ink-2">
              The current version avoids {res.advisories.fixed.map((a) => a.advisory.id).join(", ")}, so it is not just a preference.
            </p>
          ) : null}
          {res.advisories.note ? <p className="mt-2 text-[0.82rem] text-ink-3">{res.advisories.note}</p> : null}
        </section>
      ) : null}

      {res.decisions.length ? (
        <section aria-labelledby="decisions-heading">
          <div className="sec-head">
            <h2 id="decisions-heading">Decisions to read first</h2>
            <span className="sec-hint">{res.other_decisions ? `${res.other_decisions} more recorded in these files` : "active, strongest evidence first"}</span>
          </div>
          <ul className="card divide-y divide-rule">
            {res.decisions.map((g) => (
              <li key={g.decision.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Link href={`/decisions/${encodeURIComponent(g.decision.id)}`} className="text-[0.92rem] font-semibold text-ink underline-offset-4 hover:underline">
                    <InlineCode text={g.decision.text} />
                  </Link>
                  <span className="t-num text-[0.78rem] text-ink-3">since {fmtDay(g.decision.valid_from_iso)}</span>
                </div>
                {g.guards.length ? (
                  <ul className="mt-1.5 space-y-0.5 text-[0.85rem] text-ink-2">
                    {g.guards.map((x) => <li key={x} className="pl-3 [text-indent:-0.75rem]">· {x}</li>)}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby="reach-heading">
        <div className="sec-head">
          <h2 id="reach-heading">What the change reaches</h2>
          <span className="sec-hint">{reach.imports_indexed ? "static imports, up to 3 hops" : "imports not indexed yet"}</span>
        </div>
        <div className="card divide-y divide-rule">
          {hops.length ? hops.map((group) => (
            <div key={group[0].hop} className="px-4 py-3">
              <p className="text-[0.8rem] font-semibold text-ink-3">{group[0].hop === 1 ? "Imports a changed file directly" : `Through ${group[0].hop - 1} more file${group[0].hop > 2 ? "s" : ""}`} · {group.length}</p>
              <ul className="mt-1 space-y-1">
                {group.slice(0, 25).map((r) => <li key={r.path}><PathChain via={r.via} /></li>)}
              </ul>
              {group.length > 25 ? <p className="mt-1 text-[0.8rem] text-ink-3">and {group.length - 25} more</p> : null}
            </div>
          )) : (
            <p className="px-4 py-3 text-[0.88rem] text-ink-2">{reach.imports_indexed ? "No indexed file imports the changed files." : "Import connections are not indexed for this repository, so only shared commit history is shown."}</p>
          )}
          {reach.areas.length ? (
            <div className="px-4 py-3">
              <p className="text-[0.8rem] font-semibold text-ink-3">Code areas reached · {reach.areas.length}</p>
              <p className="mt-1 flex flex-wrap gap-1.5">{reach.areas.map((a) => <span key={a.name} className="chip"><span className="chip-code">{a.name}</span></span>)}</p>
            </div>
          ) : null}
          {reach.tests.length ? (
            <div className="px-4 py-3">
              <p className="text-[0.8rem] font-semibold text-ink-3">Tests to run · {reach.tests.length}</p>
              <ul className="t-code mt-1 space-y-0.5 text-[0.84rem] text-ink">{reach.tests.map((t) => <li key={t}>{t}</li>)}</ul>
            </div>
          ) : null}
          {reach.cochanged.length ? (
            <div className="px-4 py-3">
              <p className="text-[0.8rem] font-semibold text-ink-3">Usually changed in the same commits</p>
              <ul className="mt-1 space-y-0.5 text-[0.84rem]">
                {reach.cochanged.map((c) => (
                  <li key={c.path} className="flex flex-wrap gap-x-2"><span className="t-code text-ink">{c.path}</span><span className="t-num text-ink-3">{c.together} of {c.total} commits</span></li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
        {reach.truncated ? <p className="mt-2 text-[0.8rem] text-ink-3">The reach was cut at 300 files.</p> : null}
      </section>

      {res.people.length ? (
        <section aria-labelledby="people-heading">
          <div className="sec-head"><h2 id="people-heading">Who to ask for review</h2></div>
          <ul className="card divide-y divide-rule">
            {res.people.map((p) => (
              <li key={p.id} className="px-4 py-2.5 text-[0.9rem]">
                <span className="font-semibold text-ink">{p.name}</span>
                {p.login ? <a href={`https://github.com/${encodeURIComponent(p.login)}`} target="_blank" rel="noreferrer" className="ml-1.5 text-[0.82rem] text-ink-3 underline-offset-4 hover:underline">@{p.login}</a> : null}
                {p.why ? <p className="text-[0.85rem] text-ink-2">{p.why}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby="next-heading">
        <div className="sec-head"><h2 id="next-heading">Next steps</h2></div>
        <ol className="card divide-y divide-rule">
          {res.next_steps.map((s, i) => (
            <li key={s.text} className="flex gap-3 px-4 py-2.5 text-[0.9rem]">
              <span className="t-num w-5 shrink-0 text-ink-3">{i + 1}.</span>
              <span className="text-ink">
                {s.text}{" "}
                {s.href ? (
                  externalHref(s.href) ? (
                    <a href={externalHref(s.href)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-semibold text-accent underline-offset-4 hover:underline">Open <ExternalLink size={12} aria-hidden /></a>
                  ) : s.href.startsWith("/") ? (
                    <Link href={s.href} className="inline-flex items-center gap-0.5 font-semibold text-accent underline-offset-4 hover:underline">Open <ArrowUpRight size={13} aria-hidden /></Link>
                  ) : null
                ) : null}
              </span>
            </li>
          ))}
        </ol>
      </section>

      {res.targets.length ? (
        <section aria-labelledby="targets-heading">
          <div className="sec-head"><h2 id="targets-heading">What the check matched</h2><span className="sec-hint">{res.targets.length} in the graph</span></div>
          <ul className="card divide-y divide-rule">{res.targets.map((t) => <TargetRow key={t.id} t={t} />)}</ul>
          {res.unresolved_paths.length ? (
            <p className="mt-2 text-[0.84rem] text-ink-3">Not in the indexed snapshot: <span className="t-code">{res.unresolved_paths.join(", ")}</span></p>
          ) : null}
        </section>
      ) : null}

      <section aria-label="Limits" className="card-muted p-4">
        <ul className="space-y-1 text-[0.84rem] text-ink-2">{res.limits.map((l) => <li key={l}>{l}</li>)}</ul>
      </section>

      <details className="group card">
        <summary className="flex items-center justify-between px-4 py-3">
          <span className="font-semibold text-ink">Cypher <span className="text-[0.8rem] font-normal text-ink-3">· {res.cypher.length} calls{res.ms ? ` · ${Math.round(res.ms)} ms` : ""}</span></span>
          <ChevronDown size={16} className="text-ink-3 transition-transform group-open:rotate-180" aria-hidden />
        </summary>
        <div className="border-t border-rule px-4 py-4"><CypherList calls={res.cypher} /></div>
      </details>
    </div>
  );
}

function fromUrl(name: string): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get(name)?.slice(0, 4000) ?? "";
}

function PreflightWorkspace({ repo }: { repo: string }) {
  const briefing = useResource(`briefing:${repo}`, (signal) => api.briefing(repo, signal));
  const examples = preflightExamples(briefing.data, ["Remove a dependency you think is unused", "Change a configuration default"]);
  const [change, setChange] = useState(() => fromUrl("change"));
  const [paths, setPaths] = useState(() => fromUrl("paths"));
  const [state, setState] = useState<{ res?: PreflightResponse; error?: string; busy: boolean; change: string } | null>(null);
  const active = useRef<AbortController | null>(null);
  const changeId = useId();
  const pathsId = useId();
  useEffect(() => () => active.current?.abort(), []);

  // A link from the map or an entity page can name the files to check (`?paths=a,b`); it only fills the form. The
  // workspace renders after sign-in in the browser, so reading the URL while initialising state cannot mismatch.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).size) window.history.replaceState({}, "", window.location.pathname);
  }, []);

  const run = async (text: string, files: string) => {
    const list = splitPaths(files);
    if ((!text.trim() && !list.length) || state?.busy) return;
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setState({ busy: true, change: text });
    try {
      const res = await api.preflight({ repo, change: text, paths: list }, controller.signal);
      if (!controller.signal.aborted) setState({ busy: false, res, change: text });
    } catch (e) {
      if (!controller.signal.aborted) setState({ busy: false, error: errorMessage(e), change: text });
    }
  };

  const busy = state?.busy ?? false;
  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-3xl">
          <h1 className="t-display text-[2.2rem] leading-[1.04] text-ink sm:text-[2.6rem]">Check a change before you make it</h1>
          <p className="mt-2 max-w-2xl text-[0.98rem] leading-relaxed text-ink-2">
            Describe the change or paste a diff. Untangle reads the repository&apos;s history for values it would bring back, decisions that guard the
            files, what imports them, the tests to run and who to ask.
          </p>
        </div>
        <RepoSelect compact />
      </header>

      <form className="card p-4 sm:p-5" onSubmit={(e) => { e.preventDefault(); void run(change, paths); }}>
        <label htmlFor={changeId} className="text-[0.85rem] font-semibold text-ink-2">The change</label>
        <textarea
          id={changeId}
          value={change}
          onChange={(e) => setChange(e.target.value)}
          rows={7}
          maxLength={60_000}
          spellCheck={false}
          placeholder={"Set app.concurrency back to 5\n\nor paste the output of git diff"}
          className="field t-code mt-1.5 min-h-36 resize-y py-2.5 text-[0.86rem] leading-relaxed"
        />
        <label htmlFor={pathsId} className="mt-3 block text-[0.85rem] font-semibold text-ink-2">Files <span className="font-normal text-ink-3">(optional, if they are not in the diff)</span></label>
        <input id={pathsId} value={paths} onChange={(e) => setPaths(e.target.value)} placeholder="lib/router.js, package.json" autoComplete="off" className="field t-code mt-1.5 text-[0.86rem]" />
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5 text-[0.82rem] text-ink-3" aria-label="Example changes">
            <span className="mr-0.5">Try</span>
            {examples.map((x) => (
              <button key={x} type="button" className="example" disabled={busy} onClick={() => { setChange(x); setPaths(""); void run(x, ""); }}><InlineCode text={x} /></button>
            ))}
          </div>
          <button type="submit" className="btn btn-primary sm:min-w-28" disabled={busy || (!change.trim() && !splitPaths(paths).length)}>
            {busy ? "Checking…" : "Check change"}
          </button>
        </div>
      </form>

      <p aria-live="polite" className="sr-only">{busy ? "Checking the change against the repository history." : state?.res ? "Pre-flight check ready." : ""}</p>

      {state?.error ? <ErrorState title="The change could not be checked" error={state.error} onRetry={() => void run(state.change, paths)} /> : null}
      {busy ? (
        <div className="space-y-4">
          <WaitStatus label="Reading decisions, imports and shared history for the change." min={1} max={8} cancelLabel="Cancel" onCancel={() => { active.current?.abort(); setState(null); }} />
          <div className="card p-5"><SkeletonLines rows={5} /></div>
        </div>
      ) : null}
      {state?.res ? <Result res={state.res} change={state.change} /> : null}
    </div>
  );
}

export function PreflightPage() {
  const { repo, loading, error, reload } = useRepo();
  if (error) return <ErrorState title="Could not load repositories" error={error} onRetry={reload} />;
  if (loading) return <WaitStatus label="Loading repositories." min={1} max={5} />;
  if (!repo) return <NoRepository what="check a change against its history" />;
  return <PreflightWorkspace key={repo} repo={repo} />;
}

