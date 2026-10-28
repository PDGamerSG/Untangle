import Link from "next/link";
import { ArrowUpRight, ExternalLink, MessageCircleWarning, ShieldAlert, UserRound } from "lucide-react";
import { EntityChip, CitationChip } from "@/components/Chip";
import { fmtDay, predicateLabel } from "@/lib/format";
import type { PulseCategory, PulseRisk } from "@/lib/types";

const CATEGORY: Record<PulseCategory, { label: string; icon: typeof ShieldAlert; color: string; bg: string }> = {
  contradiction: { label: "Code ↔ handover conflict", icon: MessageCircleWarning, color: "text-bad", bg: "bg-bad-soft" },
  drift: { label: "Decision drift", icon: ArrowUpRight, color: "text-accent", bg: "bg-accent-soft" },
  ownership_gap: { label: "Ownership gap", icon: UserRound, color: "text-warn", bg: "bg-surface-2" },
  rationale_gap: { label: "Missing rationale", icon: ShieldAlert, color: "text-warn", bg: "bg-surface-2" },
  stale: { label: "Stale decision", icon: ShieldAlert, color: "text-ink-2", bg: "bg-surface-2" },
};

export function riskQuestion(risk: PulseRisk): string {
  const subject = risk.entity.name || risk.decision.subject || "this decision";
  if (risk.category === "contradiction") return `why does the handover call disagree with the code decision about ${subject}?`;
  if (risk.category === "drift") return `what changed around ${subject} after the recorded decision?`;
  if (risk.category === "ownership_gap") return `who should I ask about ${subject}?`;
  if (risk.category === "rationale_gap") return `why is ${subject} set this way?`;
  return `is ${subject} still current?`;
}

export function PulseRiskCard({ risk }: { risk: PulseRisk }) {
  const category = CATEGORY[risk.category];
  const Icon = category.icon;
  const question = riskQuestion(risk);
  return (
    <article id={risk.id} className="pulse-risk card overflow-hidden p-4 sm:p-5" data-risk={risk.category}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${category.bg} ${category.color}`} aria-hidden>
            <Icon size={17} />
          </span>
          <div className="min-w-0">
            <p className={`eyebrow ${category.color}`}>{category.label}</p>
            <div className="mt-1 flex min-w-0 flex-wrap items-center gap-1.5">
              <EntityChip entity={risk.entity} />
              <span className="text-[0.78rem] text-ink-3">{predicateLabel(risk.decision.predicate)}</span>
            </div>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="t-num text-[1.15rem] font-semibold text-ink">{Math.round(risk.score * 100)}%</p>
          <p className="eyebrow text-ink-3">risk score</p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
        <div>
          <p className="text-[0.76rem] font-semibold uppercase tracking-wider text-ink-3">Active decision</p>
          <p className="t-display mt-1 text-[1.35rem] text-ink">{risk.decision.object}</p>
          <p className="mt-1 text-[0.88rem] leading-relaxed text-ink-2">{risk.decision.text}</p>
        </div>
        <div className="min-w-32">
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-3" aria-label={`${Math.round(risk.score * 100)} percent risk`} role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(risk.score * 100)}>
            <div className={`h-full rounded-full ${risk.score >= 0.72 ? "bg-bad" : risk.score >= 0.3 ? "bg-warn" : "bg-accent"}`} style={{ width: `${Math.round(risk.score * 100)}%` }} />
          </div>
          <p className="t-num mt-1 text-right text-[0.72rem] text-ink-3">since {fmtDay(risk.decision.valid_from_iso)}</p>
        </div>
      </div>

      <ul className="mt-4 space-y-1.5 border-t border-rule pt-3" aria-label="Why this is a risk">
        {risk.reasons.map((reason) => <li key={reason} className="flex gap-2 text-[0.82rem] leading-relaxed text-ink-2"><span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${category.color.replace("text-", "bg-")}`} aria-hidden />{reason}</li>)}
      </ul>

      <div className="mt-4 flex flex-wrap items-center gap-1.5 text-[0.78rem] text-ink-3">
        {risk.owner ? <span className="inline-flex items-center gap-1.5"><UserRound size={13} aria-hidden /> {risk.owner.name}</span> : <span className="inline-flex items-center gap-1.5 text-warn"><UserRound size={13} aria-hidden /> No recent owner</span>}
        {risk.last_touched_iso ? <span>· touched {fmtDay(risk.last_touched_iso)}</span> : null}
        {risk.evidence.length ? <span>· {risk.evidence.length} evidence {risk.evidence.length === 1 ? "source" : "sources"}</span> : null}
        {risk.contradictions.map((ref) => <CitationChip key={ref.id} id={ref.id} citation={ref} />)}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-rule pt-3">
        <Link href={`/?question=${encodeURIComponent(question)}`} className="btn btn-primary btn-sm">Ask why <ArrowUpRight size={13} /></Link>
        <Link href={`/decisions/${encodeURIComponent(risk.decision.id)}`} className="btn btn-line btn-sm">Open evidence path <ArrowUpRight size={13} /></Link>
        {risk.evidence[0]?.url ? <a href={risk.evidence[0].url} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm">Source <ExternalLink size={13} /></a> : null}
      </div>
    </article>
  );
}
