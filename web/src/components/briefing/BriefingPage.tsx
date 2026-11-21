"use client";

import Link from "next/link";
import { ArrowUpRight, Download } from "lucide-react";
import { RepoSelect } from "@/components/repositories/RepoSelect";
import { useRepo } from "@/components/repositories/RepoContext";
import { NoRepository } from "@/components/repositories/NoRepository";
import { ListenButton } from "@/components/ask/ListenButton";
import { ErrorState, Skeleton, SkeletonLines } from "@/components/ui/states";
import { WaitStatus } from "@/components/ui/WaitStatus";
import { api, externalHref } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDay } from "@/lib/format";
import type { BriefingResponse } from "@/lib/types";
import { InlineCode } from "@/components/ask/AnswerText";

const ROOT = "(root)";

function areaName(name: string) {
  return name === ROOT ? "Top-level files" : name;
}

function Briefing({ b }: { b: BriefingResponse }) {
  const spoken = [...b.summary, ...b.guarded.slice(0, 3).map((g) => `Read before changing: ${g.decision.text}. ${g.guards[0] ?? ""}`)].join(" ");
  return (
    <div className="space-y-9">
      <section aria-labelledby="summary-heading" className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 id="summary-heading" className="text-[0.85rem] font-semibold text-ink-3">
            In short{b.head_sha ? <span className="t-num font-normal"> · snapshot {b.head_sha.slice(0, 7)}{b.indexed_at_iso ? `, indexed ${fmtDay(b.indexed_at_iso)}` : ""}</span> : null}
          </h2>
          <div className="flex flex-wrap items-center gap-2">
            <ListenButton text={spoken} />
            <a href={api.briefingMarkdownHref(b.repo)} className="btn btn-line btn-sm" download>
              <Download size={14} aria-hidden /> Download Markdown
            </a>
          </div>
        </div>
        {b.description ? <p className="mt-2 text-[0.95rem] italic text-ink-2">{b.description}</p> : null}
        <ul className="mt-3 space-y-1.5 text-[0.98rem] leading-relaxed text-ink">
          {b.summary.map((s) => <li key={s}><InlineCode text={s} /></li>)}
        </ul>
      </section>

      {b.guarded.length ? (
        <section aria-labelledby="guarded-heading">
          <div className="sec-head"><h2 id="guarded-heading">Read before changing</h2><span className="sec-hint">active decisions with the strongest evidence</span></div>
          <ol className="card divide-y divide-rule">
            {b.guarded.map((g) => {
              const source = g.decision.decided_in;
              return (
                <li key={g.decision.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <Link href={`/decisions/${encodeURIComponent(g.decision.id)}`} className="text-[0.94rem] font-semibold text-ink underline-offset-4 hover:underline"><InlineCode text={g.decision.text} /></Link>
                    <span className="t-num text-[0.78rem] text-ink-3">since {fmtDay(g.decision.valid_from_iso)}</span>
                  </div>
                  <ul className="mt-1 space-y-0.5 text-[0.86rem] text-ink-2">{g.guards.slice(0, 4).map((x) => <li key={x}>· {x}</li>)}</ul>
                  {source && externalHref(source.url) ? (
                    <a href={externalHref(source.url)} target="_blank" rel="noreferrer" className="mt-1 inline-block text-[0.8rem] font-semibold text-accent underline-offset-4 hover:underline">{source.title}</a>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </section>
      ) : null}

      {b.areas.length ? (
        <section aria-labelledby="areas-heading">
          <div className="sec-head"><h2 id="areas-heading">Code areas</h2><span className="sec-hint">by commits that touched them</span></div>
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[34rem] text-left text-[0.88rem]">
              <thead className="text-[0.78rem] text-ink-3">
                <tr className="border-b border-rule">
                  <th scope="col" className="px-4 py-2 font-semibold">Area</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Files</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Commits</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Main authors</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Decisions</th>
                  <th scope="col" className="px-4 py-2 font-semibold">Last change</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {b.areas.map((a) => (
                  <tr key={a.name}>
                    <th scope="row" className="t-code px-4 py-2 font-medium text-ink">{areaName(a.name)}</th>
                    <td className="t-num px-3 py-2 text-right text-ink-2">{a.files.toLocaleString()}</td>
                    <td className="t-num px-3 py-2 text-right text-ink-2">{a.commits.toLocaleString()}</td>
                    <td className="px-3 py-2 text-ink-2">{a.people.slice(0, 2).map((p) => `${p.name ?? p.login} ${Math.round(p.share * 100)}%`).join(", ") || "—"}</td>
                    <td className="t-num px-3 py-2 text-right text-ink-2">{a.decisions}</td>
                    <td className="t-num px-4 py-2 text-ink-3">{a.last_changed_iso ? fmtDay(a.last_changed_iso) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {b.people.length ? (
        <section aria-labelledby="people-heading">
          <div className="sec-head"><h2 id="people-heading">Who to ask</h2><span className="sec-hint">recent authors first</span></div>
          <ul className="card divide-y divide-rule">
            {b.people.map((p) => (
              <li key={p.id} className="flex flex-wrap items-baseline justify-between gap-2 px-4 py-2.5 text-[0.9rem]">
                <span>
                  <span className="font-semibold text-ink">{p.name ?? p.login}</span>
                  {p.login ? <a href={`https://github.com/${encodeURIComponent(p.login)}`} target="_blank" rel="noreferrer" className="ml-1.5 text-[0.82rem] text-ink-3 underline-offset-4 hover:underline">@{p.login}</a> : null}
                  {p.areas.length ? <span className="t-code ml-2 text-[0.82rem] text-ink-2">{p.areas.slice(0, 3).map(areaName).join(", ")}</span> : null}
                </span>
                <span className="t-num text-[0.8rem] text-ink-3">{p.commits.toLocaleString()} recent commits</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {b.changes.length ? (
        <section aria-labelledby="changes-heading">
          <div className="sec-head"><h2 id="changes-heading">Recently replaced</h2></div>
          <ul className="card divide-y divide-rule">
            {b.changes.map((c) => (
              <li key={c.newer.id + c.older.id} className="px-4 py-2.5 text-[0.88rem]">
                <p className="t-num text-[0.78rem] text-ink-3">{c.at_iso ? fmtDay(c.at_iso) : ""}</p>
                <p className="mt-0.5 text-ink-2"><span className="mark-superseded"><InlineCode text={c.older.text} /></span></p>
                <p className="text-ink">
                  <Link href={`/decisions/${encodeURIComponent(c.newer.id)}`} className="underline-offset-4 hover:underline"><InlineCode text={c.newer.text} /></Link>
                </p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {b.questions.length ? (
        <section aria-labelledby="questions-heading">
          <div className="sec-head"><h2 id="questions-heading">Ask next</h2></div>
          <div className="flex flex-wrap gap-1.5">
            {b.questions.map((q) => (
              <Link key={q} href={`/ask?question=${encodeURIComponent(q)}`} className="example">{q}</Link>
            ))}
            <Link href="/preflight" className="inline-flex items-center gap-1 px-2 text-[0.85rem] font-semibold text-accent underline-offset-4 hover:underline">
              Check a change <ArrowUpRight size={13} aria-hidden />
            </Link>
          </div>
        </section>
      ) : null}

      <section aria-label="Limits" className="card-muted p-4">
        <ul className="space-y-1 text-[0.84rem] text-ink-2">{b.limits.map((l) => <li key={l}>{l}</li>)}</ul>
      </section>
    </div>
  );
}

export function BriefingPage() {
  const { repo } = useRepo();
  const res = useResource(repo ? `briefing:${repo}` : null, (signal) => api.briefing(repo!, signal));
  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-3xl">
          <h1 className="t-display text-[2.2rem] leading-[1.04] text-ink sm:text-[2.6rem]">Your first day in {repo ?? "a repository"}</h1>
          <p className="mt-2 max-w-2xl text-[0.98rem] leading-relaxed text-ink-2">
            Where the change happens, who wrote it, which decisions to read before touching anything, and what was replaced recently. Built from the
            recorded history only.
          </p>
        </div>
        <RepoSelect compact />
      </header>
      {!repo ? (
        <NoRepository what="get a briefing" />
      ) : res.error ? (
        <ErrorState title="Could not build the briefing" error={res.error} onRetry={res.reload} />
      ) : res.data ? (
        <Briefing b={res.data} />
      ) : (
        <div className="space-y-4">
          <WaitStatus label="Reading code areas, decisions and authors." min={1} max={10} />
          <div className="card p-5"><Skeleton className="h-4 w-40" /><SkeletonLines rows={4} className="mt-4" /></div>
        </div>
      )}
    </div>
  );
}
