import { InlineCode } from "./AnswerText";
import Link from "next/link";
import { ChevronRight, ExternalLink } from "lucide-react";
import { StatusMark } from "@/components/DecisionCard";
import { SectionTitle } from "@/components/states";
import { hrefFor } from "@/lib/api";
import { fmtDay, fmtDateTime, kindFromId } from "@/lib/format";
import type { EvidenceStep } from "@/lib/types";

const ROLE_LABEL: Record<EvidenceStep["role"], string> = {
  decision: "Decision",
  discussion: "Discussion",
  incident: "Incident",
  person: "Person",
  date: "Date",
};

const ROLE_KIND: Record<EvidenceStep["role"], string> = {
  decision: "decision",
  discussion: "pr",
  incident: "issue",
  person: "person",
  date: "entity",
};

function StepLink({ id, url, children }: { id: string; url?: string | null; children: React.ReactNode }) {
  const link = hrefFor(id, kindFromId(id), url);
  if (!link) return <>{children}</>;
  if (link.external)
    return (
      <a href={link.href} target="_blank" rel="noreferrer" className="inline-flex items-start gap-1 underline-offset-4 hover:underline">
        {children}
        <ExternalLink size={12} className="mt-1 shrink-0" aria-hidden />
      </a>
    );
  return (
    <Link href={link.href} className="underline-offset-4 hover:underline">
      {children}
    </Link>
  );
}

export function EvidenceChain({ steps }: { steps: EvidenceStep[] }) {
  if (!steps.length) return null;
  return (
    <section aria-label="Evidence chain">
      <SectionTitle hint={`${steps.length} ${steps.length === 1 ? "step" : "steps"}`}>Evidence chain</SectionTitle>
      <ol className="flex snap-x gap-0 overflow-x-auto overflow-y-hidden pb-2">
        {steps.map((s, i) => {
          const kind = s.role === "discussion" ? kindFromId(s.id) : ROLE_KIND[s.role];
          return (
            <li key={`${s.role}-${i}`} className="flex min-w-[13rem] max-w-[17rem] shrink-0 snap-start items-stretch">
              <div className="card flex w-full min-w-0 flex-col p-3" data-kind={kind}>
                <p className="flex items-center gap-1.5 text-[0.68rem] font-bold uppercase tracking-wider" style={{ color: "var(--c)" }}>
                  <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: "var(--c)" }} aria-hidden />
                  {ROLE_LABEL[s.role]}
                </p>
                <div className="mt-1.5 min-w-0 break-words text-[0.88rem] leading-snug text-ink">
                  {s.role === "decision" ? (
                    <>
                      <StepLink id={s.id}>
                        <InlineCode text={s.title ?? ""} />
                      </StepLink>
                      <div className="mt-1.5">
                        <StatusMark status={s.status} validTo={s.valid_to_iso} />
                      </div>
                      <p className="t-num mt-1 text-[0.76rem] text-ink-3">
                        {s.valid_to_iso ? `${fmtDay(s.valid_from_iso)} → ${fmtDay(s.valid_to_iso)}` : `Since ${fmtDay(s.valid_from_iso)}`}
                      </p>
                    </>
                  ) : s.role === "discussion" ? (
                    <>
                      <StepLink id={s.id} url={s.url}>
                        {s.title}
                      </StepLink>
                      {s.excerpt ? <p className="mt-1.5 line-clamp-4 text-[0.8rem] italic leading-snug text-ink-2">“{s.excerpt}”</p> : null}
                    </>
                  ) : s.role === "incident" ? (
                    <StepLink id={s.id} url={s.url}>
                      {s.title}
                    </StepLink>
                  ) : s.role === "person" ? (
                    <>
                      <StepLink id={s.id} url={/^person:gh:/.test(s.id) ? `https://github.com/${s.id.slice("person:gh:".length)}` : null}>
                        <span className="font-semibold">{s.name}</span>
                      </StepLink>
                      {s.why ? <p className="mt-1 text-[0.8rem] leading-snug text-ink-2">{s.why}</p> : null}
                    </>
                  ) : (
                    <>
                      <span className="t-num font-semibold">{fmtDay(s.iso)}</span>
                      <p className="t-num mt-1 text-[0.76rem] text-ink-3">{fmtDateTime(s.iso)}</p>
                    </>
                  )}
                </div>
              </div>
              {i < steps.length - 1 ? (
                <span className="flex w-6 shrink-0 items-center justify-center text-ink-3" aria-hidden>
                  <ChevronRight size={16} />
                </span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
