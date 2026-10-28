import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { CitationChip, EntityChip } from "./Chip";
import { fmtDay, predicateLabel, signalLabel } from "@/lib/format";
import type { DecisionCard as DecisionCardT } from "@/lib/types";

export function StatusMark({ status, validTo }: { status: string; validTo?: string | null }) {
  const label = status === "active" ? "Active" : status === "superseded" ? (validTo ? `Superseded ${fmtDay(validTo)}` : "Superseded") : "Retracted";
  return (
    <span className="inline-flex items-center gap-1.5 text-[0.8rem] font-semibold text-ink-2">
      <span className="status-dot" data-status={status} aria-hidden />
      {label}
    </span>
  );
}

export function DecisionCard({ decision, muted = false, highlight = false }: { decision: DecisionCardT; muted?: boolean; highlight?: boolean }) {
  const d = decision;
  const dead = muted || d.status !== "active";
  return (
    <article className={`${dead ? "card-muted" : "card"} ${highlight ? "ring-2 ring-accent/40" : ""} p-4`}>
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <p className="text-[0.78rem] text-ink-3">
          <span className="font-semibold text-ink-2">{d.subject}</span> · {predicateLabel(d.predicate)}
        </p>
        <StatusMark status={d.status} validTo={d.valid_to_iso} />
      </div>
      <p className={`t-display mt-1.5 text-[1.35rem] ${dead ? "mark-superseded" : "text-ink"}`}>{d.object}</p>
      <p className="mt-2 text-[0.92rem] leading-relaxed text-ink-2">{d.text}</p>
      {d.rationale ? (
        <p className="mt-2 border-l-2 border-rule-strong pl-3 text-[0.88rem] italic leading-relaxed text-ink-2">{d.rationale}</p>
      ) : (
        <p className="mt-2 text-[0.82rem] text-ink-3">No reason recorded.</p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {d.about.slice(0, 3).map((e) => (
          <EntityChip key={e.id} entity={e} />
        ))}
        {d.decided_in ? <CitationChip id={d.decided_in.id} citation={{ kind: d.decided_in.kind, title: d.decided_in.title, url: d.decided_in.url }} /> : null}
        {d.stated_by ? <CitationChip id={d.stated_by.id} citation={{ kind: "person", title: d.stated_by.name, url: d.stated_by.login ? `https://github.com/${d.stated_by.login}` : null }} /> : null}
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[0.78rem] text-ink-3">
        <span className="t-num">
          {d.valid_to_iso ? `${fmtDay(d.valid_from_iso)} → ${fmtDay(d.valid_to_iso)}` : `Since ${fmtDay(d.valid_from_iso)}`} · {signalLabel(d.signal)} · confidence{" "}
          {Math.round(d.confidence * 100)}%
        </span>
        <Link href={`/decisions/${encodeURIComponent(d.id)}`} className="inline-flex items-center gap-0.5 font-semibold text-ink-2 underline-offset-4 hover:underline">
          Why path <ArrowUpRight size={13} />
        </Link>
      </div>
    </article>
  );
}
