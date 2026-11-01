"use client";

import { useId, useState } from "react";
import { Search } from "lucide-react";
import { PulseRiskCard } from "./PulseRiskCard";
import { EmptyState } from "./states";
import { ExportBrief } from "./ExportBrief";
import { briefFilename, matchesDecision, riskBrief } from "@/lib/evidence-brief";
import { fmtDateTime } from "@/lib/format";
import type { PulseCategory, PulseResponse } from "@/lib/types";

const CATEGORIES: { value: PulseCategory; label: string }[] = [
  { value: "contradiction", label: "Conflicts" },
  { value: "drift", label: "Code drift" },
  { value: "ownership_gap", label: "Ownership gaps" },
  { value: "rationale_gap", label: "Missing reasons" },
  { value: "stale", label: "Stale decisions" },
];

export function PulseQueue({ repo, data }: { repo: string; data: PulseResponse }) {
  const [category, setCategory] = useState<PulseCategory | "all">("all");
  const [query, setQuery] = useState("");
  const [criticalOnly, setCriticalOnly] = useState(false);
  const searchId = useId();
  const filtered = data.risks.filter(r => (category === "all" || r.category === category)
    && (!criticalOnly || r.score >= 0.72)
    && (matchesDecision(r.decision, query) || [r.entity.name, r.entity.path, r.owner?.name, r.owner?.login, ...r.reasons].join(" ").toLowerCase().includes(query.toLowerCase().trim())));
  return (
    <section aria-labelledby="risk-queue" className="space-y-4">
      <div className="sec-head">
        <div><h2 id="risk-queue">Knowledge risks</h2><p className="mt-1 text-[0.8rem] text-ink-3">Prioritize a conflict, find its evidence, and bring the right person into the conversation.</p></div>
        <ExportBrief label="Export risks" filename={briefFilename(repo, "risks")} build={origin => riskBrief(repo, data.generated_at_iso, filtered, origin)} disabled={!filtered.length} />
      </div>
      <div className="card space-y-3 p-4">
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Risk category">
          <button type="button" className="filter-pill" aria-pressed={category === "all"} onClick={() => setCategory("all")}>All risks ({data.risks.length})</button>
          {CATEGORIES.map(c => <button key={c.value} type="button" className="filter-pill" aria-pressed={category === c.value} onClick={() => setCategory(c.value)}>{c.label} ({data.risks.filter(r => r.category === c.value).length})</button>)}
        </div>
        <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-3">
          <div className="relative min-w-0 flex-1 basis-60"><label htmlFor={searchId} className="sr-only">Filter risks</label><Search size={16} aria-hidden className="pointer-events-none absolute left-3 top-3 text-ink-3" /><input id={searchId} type="search" className="field pl-9" placeholder="Find a file, decision or owner" value={query} onChange={e => setQuery(e.target.value)} /></div>
          <label className="flex items-center gap-2 text-[0.85rem] text-ink-2"><input type="checkbox" className="h-4 w-4 accent-[var(--accent)]" checked={criticalOnly} onChange={e => setCriticalOnly(e.target.checked)} />Critical only</label>
        </div>
      </div>
      <div className="flex flex-wrap justify-between gap-2 text-[0.78rem] text-ink-3"><p role="status">Showing {filtered.length} of {data.risks.length} returned risks</p><p>Checked {fmtDateTime(data.generated_at_iso)}</p></div>
      {filtered.length ? <div className="grid gap-4 xl:grid-cols-2">{filtered.map(risk => <PulseRiskCard key={risk.id} risk={risk} />)}</div>
        : <EmptyState title="No risks match these filters."><button className="btn btn-line btn-sm mt-3" type="button" onClick={() => { setQuery(""); setCategory("all"); setCriticalOnly(false); }}>Clear risk filters</button></EmptyState>}
      <p className="text-[0.78rem] leading-relaxed text-ink-3">This is the returned priority queue, not a complete repository audit. Risk scores rank recorded signals; they are not probabilities. Exports contain only the risks shown by your filters.</p>
    </section>
  );
}
