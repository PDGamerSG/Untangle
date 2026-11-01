"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, FileText, GitBranch, Search, UserRound } from "lucide-react";
import { CitationChip, EntityChip } from "./Chip";
import { StatusMark } from "./DecisionCard";
import { EmptyState } from "./states";
import { ExportBrief } from "./ExportBrief";
import { briefFilename, decisionBrief, matchesDecision, snapshotDecisions, type SnapshotDecision } from "@/lib/evidence-brief";
import { fmtDay, predicateLabel, signalLabel } from "@/lib/format";
import type { Timeline } from "@/lib/types";

const KINDS: Record<string, string> = { config_value: "Configuration", dependency: "Dependencies", adr: "Design records", kt: "Handovers", change: "Changes", rationale: "Rationale", revert: "Reverts" };

function Inspector({ entry, atIso }: { entry: SnapshotDecision; atIso: string }) {
  const d = entry.decision;
  const day = atIso.slice(0, 10);
  const question = `why is ${d.subject} like this?`;
  return (
    <section aria-label="Selected decision" className="min-w-0 space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[0.8rem]">
        <span className={entry.inForce ? "font-semibold text-accent" : "text-ink-3"}>
          {entry.inForce ? `In force on ${fmtDay(atIso)}` : `Not in force on ${fmtDay(atIso)}`}
        </span>
        <StatusMark status={d.status} validTo={d.valid_to_iso} />
      </div>
      <div>
        <h3 className="break-words text-[1rem] font-semibold text-ink">{d.subject}</h3>
        <p className="mt-1 text-[0.8rem] text-ink-3">{predicateLabel(d.predicate)}</p>
        <p className="t-display mt-3 break-words text-[2rem] leading-tight text-accent">{d.object}</p>
        <p className="mt-3 break-words text-[0.9rem] leading-relaxed text-ink-2">{d.text}</p>
      </div>
      <div className="rounded-lg border border-rule bg-surface-2 p-4">
        <p className="text-[0.8rem] font-semibold text-ink">Recorded reason</p>
        <p className="mt-1 break-words text-[0.9rem] leading-relaxed text-ink-2">{d.rationale || "No reason recorded."}</p>
      </div>
      <div className="evidence-connections" aria-label="Evidence connections">
        <div className="evidence-connection">
          <FileText size={16} aria-hidden />
          <div className="min-w-0"><p className="text-[0.8rem] font-semibold">Recorded in</p>
            {d.decided_in ? <div className="mt-1.5"><CitationChip id={d.decided_in.id} citation={d.decided_in} /><p className="mt-1 break-words text-[0.82rem] text-ink-2">{d.decided_in.title}</p></div> : <p className="mt-1 text-[0.82rem] text-ink-3">No source linked.</p>}
          </div>
        </div>
        <div className="evidence-connection">
          <GitBranch size={16} aria-hidden />
          <div className="min-w-0"><p className="text-[0.8rem] font-semibold">Connected code</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">{d.about.length ? d.about.map(e => <EntityChip entity={e} key={e.id} />) : <p className="text-[0.82rem] text-ink-3">No code entity linked.</p>}</div>
          </div>
        </div>
        <div className="evidence-connection">
          <UserRound size={16} aria-hidden />
          <div><p className="text-[0.8rem] font-semibold">Stated by</p><p className="mt-1 break-words text-[0.85rem] text-ink-2">{d.stated_by?.name || d.stated_by?.login || "No person recorded"}</p></div>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-3 border-t border-rule pt-4 text-[0.8rem]">
        <div><dt className="text-ink-3">Recorded from</dt><dd className="mt-1 text-ink">{fmtDay(d.valid_from_iso)}</dd></div>
        <div><dt className="text-ink-3">Extraction signal</dt><dd className="mt-1 text-ink">{signalLabel(d.signal)}</dd></div>
      </dl>
      <div className="flex flex-wrap gap-2">
        <Link href={`/decisions/${encodeURIComponent(d.id)}`} className="btn btn-primary btn-sm">Open evidence path <ArrowUpRight size={14} aria-hidden /></Link>
        <Link href={`/ask?${new URLSearchParams({ question, at: day })}`} className="btn btn-line btn-sm">Ask about this date <ArrowUpRight size={14} aria-hidden /></Link>
      </div>
    </section>
  );
}

export function DecisionWorkbench({ repo, snapshot }: { repo: string; snapshot: Timeline }) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [group, setGroup] = useState("all");
  const [selection, setSelection] = useState<string | null>(null);
  const queryId = useId();
  const kindId = useId();
  const entries = snapshotDecisions(snapshot);
  const kinds = [...new Set(entries.map(e => e.decision.kind))].sort();
  const filtered = entries.filter(e => (kind === "all" || kind === e.decision.kind)
    && (group === "all" || (group === "in-force" ? e.inForce : e.replacedSince)) && matchesDecision(e.decision, query));
  const selected = filtered.find(e => e.decision.id === selection) ?? filtered[0];
  const tabs = [
    { value: "all", label: "All loaded", count: entries.length },
    { value: "in-force", label: "In force", count: entries.filter(e => e.inForce).length },
    { value: "replaced", label: "Replaced since", count: entries.filter(e => e.replacedSince).length },
  ];

  return (
    <section aria-label="Decision workbench" className="space-y-4">
      <div className="sec-head">
        <div><h2>Decision workbench</h2><p className="mt-1 text-[0.85rem] text-ink-3">Inspect the evidence behind the snapshot of {fmtDay(snapshot.at_iso)}.</p></div>
        <ExportBrief label="Export view" filename={briefFilename(repo, `decisions-${snapshot.at_iso.slice(0, 10)}`)} build={origin => decisionBrief(repo, snapshot.at_iso, filtered, origin)} disabled={!filtered.length} />
      </div>
      <div className="workbench">
        <div className="flex flex-wrap gap-3 border-b border-rule bg-surface-2/50 p-4">
          <div className="min-w-0 flex-1 basis-60">
            <label htmlFor={queryId} className="sr-only">Filter decisions</label>
            <div className="relative"><Search size={16} className="pointer-events-none absolute left-3 top-3 text-ink-3" aria-hidden /><input id={queryId} type="search" className="field pl-9" placeholder="Find a file, value, reason or person" value={query} onChange={e => setQuery(e.target.value)} /></div>
          </div>
          <div className="min-w-0"><label htmlFor={kindId} className="sr-only">Decision type</label><select id={kindId} className="field" value={kind} onChange={e => setKind(e.target.value)}><option value="all">All decision types</option>{kinds.map(k => <option key={k} value={k}>{KINDS[k] ?? k}</option>)}</select></div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-4 py-3">
          <div className="flex flex-wrap gap-1" role="group" aria-label="Decision scope">{tabs.map(tab => <button key={tab.value} type="button" className="filter-pill" aria-pressed={group === tab.value} onClick={() => setGroup(tab.value)}>{tab.label} <span className="t-num">{tab.count}</span></button>)}</div>
          <p className="text-[0.78rem] text-ink-3" role="status">{filtered.length} of {entries.length} loaded</p>
        </div>
        {filtered.length ? (
          <div className="grid min-w-0 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <ul aria-label="Matching decisions" className="max-h-[34rem] min-w-0 overflow-y-auto border-b border-rule xl:border-b-0 xl:border-r">
              {filtered.map(({ decision: d, inForce }) => (
                <li key={d.id} className="border-b border-rule last:border-b-0">
                  <button type="button" className="decision-row" aria-label={`Inspect ${d.subject}`} aria-pressed={selected?.decision.id === d.id} onClick={() => setSelection(d.id)}>
                    <span className="flex items-center justify-between gap-2 text-[0.76rem] text-ink-3"><span>{KINDS[d.kind] ?? d.kind}</span><span className="t-num">{fmtDay(d.valid_from_iso)}</span></span>
                    <span className="mt-2 block break-words text-[0.9rem] font-semibold text-ink">{d.subject}</span>
                    <span className="mt-1 line-clamp-2 break-words text-[0.85rem] leading-relaxed text-ink-2">{d.object}</span>
                    <span className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[0.75rem] text-ink-3"><span>{inForce ? "In force at this date" : "Later record"}</span><span>{d.rationale ? "Reason recorded" : "Reason missing"}</span></span>
                  </button>
                </li>
              ))}
            </ul>
            {selected ? <Inspector entry={selected} atIso={snapshot.at_iso} /> : null}
          </div>
        ) : <div className="p-4"><EmptyState title={entries.length ? "No decisions match these filters." : "No decisions recorded for this snapshot."}>{entries.length ? <button type="button" className="btn btn-line btn-sm mt-3" onClick={() => { setQuery(""); setKind("all"); setGroup("all"); }}>Clear decision filters</button> : "Choose another date to explore the repository's history."}</EmptyState></div>}
      </div>
      <p className="text-[0.78rem] leading-relaxed text-ink-3">This snapshot contains up to 100 decisions. Search, counts and export use the loaded records. “In force” refers to the selected date; current status may have changed since then.</p>
    </section>
  );
}
