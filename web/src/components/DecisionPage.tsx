"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronDown, ExternalLink } from "lucide-react";
import { CitationChip } from "./Chip";
import { DecisionCard, StatusMark } from "./DecisionCard";
import { CypherList } from "./ask/WhyPanel";
import { EmptyState, ErrorState, SectionTitle, Skeleton, SkeletonLines } from "./states";
import { api, hrefFor } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDateTime, fmtDay, normaliseKind, predicateLabel, signalLabel } from "@/lib/format";
import type { DecisionCard as DecisionCardT, Ref } from "@/lib/types";

function RefRow({ r }: { r: Ref }) {
  const kind = normaliseKind(r.kind, r.id);
  const link = hrefFor(r.id, kind, r.url);
  return (
    <li className="flex flex-col items-start gap-x-3 gap-y-1 px-4 py-3 sm:flex-row">
      <CitationChip id={r.id} citation={{ kind, title: r.title, url: r.url }} />
      <div className="min-w-0 flex-1 text-[0.9rem]">
        <p className="text-ink">
          {link ? (
            link.external ? (
              <a href={link.href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline-offset-4 hover:underline">
                {r.title} <ExternalLink size={12} aria-hidden />
              </a>
            ) : (
              <Link href={link.href} className="underline-offset-4 hover:underline">
                {r.title}
              </Link>
            )
          ) : (
            r.title
          )}
        </p>
        {r.excerpt ? <blockquote className="mt-1 border-l-2 border-rule-strong pl-3 text-[0.86rem] italic leading-relaxed text-ink-2">{r.excerpt}</blockquote> : null}
        {r.author || r.at_iso ? (
          <p className="t-num mt-1 text-[0.78rem] text-ink-3">
            {r.author ? `${r.author}` : ""}
            {r.author && r.at_iso ? " · " : ""}
            {r.at_iso ? fmtDateTime(r.at_iso) : ""}
          </p>
        ) : null}
      </div>
    </li>
  );
}

function ChainItem({ d, isThis }: { d: DecisionCardT; isThis: boolean }) {
  const active = d.status === "active";
  return (
    <li className="relative pb-6 pl-7 last:pb-0">
      <span
        aria-hidden
        className={`absolute left-[3px] top-1.5 h-[11px] w-[11px] rounded-full border-2 ${active ? "border-ok bg-ok" : "border-ink-3 bg-surface"} ${isThis ? "ring-4 ring-accent/30" : ""}`}
      />
      <div className={isThis ? "card p-3.5 ring-2 ring-accent/40" : "p-0"}>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {isThis ? (
            <span className={`t-display text-[1.15rem] ${active ? "text-ink" : "mark-superseded"}`}>{d.object}</span>
          ) : (
            <Link href={`/decisions/${encodeURIComponent(d.id)}`} className={`t-display text-[1.15rem] underline-offset-4 hover:underline ${active ? "text-ink" : "mark-superseded"}`}>
              {d.object}
            </Link>
          )}
          <StatusMark status={d.status} validTo={d.valid_to_iso} />
          {isThis ? <span className="text-[0.76rem] text-ink-3">this decision</span> : null}
        </p>
        <p className="t-num mt-1 text-[0.8rem] text-ink-3">
          {d.valid_to_iso ? `${fmtDay(d.valid_from_iso)} → ${fmtDay(d.valid_to_iso)}` : `Since ${fmtDay(d.valid_from_iso)}`}
          {d.stated_by ? ` · ${d.stated_by.name}` : ""}
          {d.decided_in ? ` · ${d.decided_in.title}` : ""}
          {` · ${signalLabel(d.signal)}`}
        </p>
        <p className="mt-1 text-[0.86rem] text-ink-2">{d.text}</p>
      </div>
    </li>
  );
}

export function DecisionPage() {
  const params = useParams<{ id: string }>();
  const id = (() => {
    try {
      return decodeURIComponent(params.id ?? "");
    } catch {
      return params.id ?? "";
    }
  })();
  const res = useResource(id ? `decision:${id}` : null, (signal) => api.decision(id, signal));

  if (res.loading)
    return (
      <div className="space-y-6" role="status" aria-label="Loading decision">
        <Skeleton className="h-3 w-32" />
        <div className="card p-4">
          <Skeleton className="h-3 w-40" />
          <Skeleton className="mt-3 h-7 w-1/3" />
          <SkeletonLines rows={3} className="mt-4" />
        </div>
        <SkeletonLines rows={4} />
      </div>
    );
  if (res.error)
    return res.errorStatus === 404 ? (
      <EmptyState title="No such decision">
        <code className="t-code">{id}</code> is not in the graph for this repository.{" "}
        <Link href="/" className="underline">
          Ask a question
        </Link>
      </EmptyState>
    ) : (
      <ErrorState title="Could not load the decision" error={res.error} onRetry={res.reload} />
    );
  const w = res.data;
  if (!w) return null;
  const d = w.decision;
  const chain: DecisionCardT[] = [
    ...[...w.older].sort((a, b) => Date.parse(a.valid_from_iso) - Date.parse(b.valid_from_iso)),
    d,
    ...[...w.newer].sort((a, b) => Date.parse(a.valid_from_iso) - Date.parse(b.valid_from_iso)),
  ];

  return (
    <div className="space-y-8">
      <nav aria-label="Breadcrumb" className="text-[0.82rem] text-ink-3">
        <Link href="/" className="hover:underline">
          Ask
        </Link>{" "}
        / <span className="text-ink-2">Decision</span>
      </nav>

      <header>
        <p className="text-[0.82rem] text-ink-3">
          {d.kind !== d.predicate ? `${d.kind.replaceAll("_", " ")} decision · ` : ""}
          <span className="font-semibold text-ink-2">{d.subject}</span> · {predicateLabel(d.predicate)}
        </p>
        <h1 className={`t-display mt-1 text-[2rem] sm:text-[2.4rem] ${d.status === "active" ? "text-ink" : "mark-superseded"}`}>{d.object}</h1>
      </header>

      <DecisionCard decision={d} highlight />

      <section aria-label="Evidence">
        <SectionTitle hint={`${w.evidence.length} ${w.evidence.length === 1 ? "source" : "sources"}`}>Evidence</SectionTitle>
        {w.evidence.length ? (
          <ul className="card divide-y divide-rule">
            {w.evidence.map((r) => (
              <RefRow key={r.id} r={r} />
            ))}
          </ul>
        ) : (
          <EmptyState title="No evidence linked" />
        )}
      </section>

      <section aria-label="History of this decision">
        <SectionTitle hint="oldest first">History, older → newer</SectionTitle>
        <ol className="relative ml-1 border-l border-rule-strong pt-1">
          {chain.map((c) => (
            <ChainItem key={c.id} d={c} isThis={c.id === d.id} />
          ))}
        </ol>
        {chain.length === 1 ? <p className="mt-2 text-[0.82rem] text-ink-3">Nothing has superseded this decision, and it superseded nothing.</p> : null}
      </section>

      {w.motivated_by.length ? (
        <section aria-label="Motivated by">
          <SectionTitle>Motivated by</SectionTitle>
          <ul className="card divide-y divide-rule">
            {w.motivated_by.map((r) => (
              <RefRow key={r.id} r={r} />
            ))}
          </ul>
        </section>
      ) : null}

      {w.implemented_by.length ? (
        <section aria-label="Implemented by">
          <SectionTitle hint={`${w.implemented_by.length} ${w.implemented_by.length === 1 ? "commit" : "commits"}`}>Implemented by</SectionTitle>
          <ul className="card divide-y divide-rule">
            {w.implemented_by.map((r) => (
              <RefRow key={r.id} r={r} />
            ))}
          </ul>
        </section>
      ) : null}

      <details className="group card">
        <summary className="flex items-center justify-between px-4 py-3">
          <span className="font-semibold text-ink">
            Cypher <span className="text-[0.8rem] font-normal text-ink-3">· {w.cypher.length} {w.cypher.length === 1 ? "call" : "calls"}</span>
          </span>
          <ChevronDown size={16} className="text-ink-3 transition-transform group-open:rotate-180" aria-hidden />
        </summary>
        <div className="border-t border-rule px-4 py-4">
          <CypherList calls={w.cypher} />
        </div>
      </details>
      <p className="t-code break-all text-[0.72rem] text-ink-3">{d.id}</p>
    </div>
  );
}
