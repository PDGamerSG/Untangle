import { CircleSlash } from "lucide-react";
import { CitationChip, EntityChip } from "@/components/Chip";
import { CopyButton } from "@/components/CopyButton";
import { SectionTitle } from "@/components/states";
import { AnswerText } from "./AnswerText";
import { BaselineCompare } from "./BaselineCompare";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { EvidenceChain } from "./EvidenceChain";
import { SupersessionBanner } from "./SupersessionBanner";
import { WhyPanel } from "./WhyPanel";
import { fmtDay, KIND_LABEL, normaliseKind } from "@/lib/format";
import type { AskResponse } from "@/lib/types";

function Refusal({ res }: { res: AskResponse }) {
  return (
    <div className="card-muted p-5">
      <p className="flex items-center gap-2 text-[0.78rem] font-bold uppercase tracking-wider text-ink-3">
        <CircleSlash size={14} aria-hidden /> Refused
      </p>
      <h3 className="t-display mt-2 text-[1.6rem] text-ink-2">Nothing in the graph answers this.</h3>
      <AnswerText text={res.answer} citations={res.citations} className="mt-2 text-[0.95rem] leading-relaxed text-ink-2" />
      {res.closest?.length ? (
        <div className="mt-4">
          <p className="text-[0.78rem] font-semibold text-ink-3">Closest related entities</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {res.closest.map((e) => (
              <EntityChip key={e.id} entity={e} />
            ))}
          </div>
        </div>
      ) : null}
      {res.ask ? (
        <div className="mt-3">
          <p className="text-[0.78rem] font-semibold text-ink-3">Person to ask</p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-[0.9rem] text-ink">
            <CitationChip id={res.ask.id} citation={{ kind: "person", title: res.ask.name, url: res.ask.login ? `https://github.com/${res.ask.login}` : null }} />
            {res.ask.why ? <span className="text-ink-2">{res.ask.why}</span> : null}
          </p>
        </div>
      ) : null}
      {res.confidence.reasons.length ? (
        <div className="mt-4">
          <p className="text-[0.78rem] font-semibold text-ink-3">Why it refused</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[0.85rem] text-ink-2">
            {res.confidence.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="mt-4 text-[0.78rem] text-ink-3">No confidence score is shown for a refusal: there is no anchored evidence to score.</p>
    </div>
  );
}

export function AnswerCard({ res, atIso }: { res: AskResponse; atIso: string | null }) {
  const citations = Object.entries(res.citations);
  return (
    <article className="space-y-6" aria-label="Answer">
      <header>
        <p className="eyebrow flex flex-wrap items-center gap-x-3 gap-y-1 text-ink-3">
          <span className="t-code">{res.repo}</span>
          {atIso ? <span className="rounded-md bg-surface-2 px-2 py-0.5 text-ink-2">as of {fmtDay(atIso)}</span> : null}
          {res.mode === "both" ? <span className="rounded-md bg-surface-2 px-2 py-0.5 text-ink-2">compared with vector-only</span> : null}
        </p>
        <h2 className="t-display mt-1 text-[1.7rem] text-ink sm:text-[2rem]">{res.question}</h2>
        <div className="mt-3 flex flex-wrap items-center gap-1 rounded-lg border border-rule bg-surface-2/60 p-1" aria-label="Answer actions">
          <CopyButton text={res.question} label="Copy question" />
          <CopyButton text={res.answer} label="Copy answer" />
          <span className="ml-1 hidden text-[0.76rem] text-ink-3 sm:inline">Keep the evidence close when you share it.</span>
        </div>
      </header>

      {res.refused ? (
        <Refusal res={res} />
      ) : (
        <div className="card overflow-hidden p-5 sm:p-6">
          <p className="eyebrow text-accent">Answer from the graph</p>
          <AnswerText text={res.answer} citations={res.citations} className="mt-2 break-words text-[1.08rem] leading-[1.7] text-ink" />
          {res.entities.length ? (
            <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-rule pt-3">
              <span className="mr-1 text-[0.76rem] font-semibold uppercase tracking-wider text-ink-3">About</span>
              {res.entities.map((e) => (
                <EntityChip key={e.id} entity={e} />
              ))}
            </div>
          ) : null}
        </div>
      )}

      {res.baseline ? <BaselineCompare res={res} /> : null}

      {!res.refused ? (
        <>
          <EvidenceChain steps={res.evidence_chain} />
          <SupersessionBanner items={res.supersession} />
          <ConfidenceMeter confidence={res.confidence} />
          {citations.length ? (
            <section aria-label="Sources">
              <SectionTitle hint={`${citations.length} cited`}>Sources</SectionTitle>
              <ul className="card divide-y divide-rule">
                {citations.map(([id, c]) => {
                  const kind = normaliseKind(c.kind, id);
                  return (
                    <li key={id} className="flex flex-col items-start gap-x-3 gap-y-1 px-4 py-2.5 text-[0.88rem] sm:flex-row">
                      <CitationChip id={id} citation={c} />
                      <div className="min-w-0 flex-1">
                        <p className="text-ink">
                          <span className="sr-only">{KIND_LABEL[kind]}: </span>
                          {c.title}
                        </p>
                        {c.excerpt ? <p className="mt-0.5 line-clamp-2 text-[0.82rem] italic text-ink-2">“{c.excerpt}”</p> : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ) : null}
        </>
      ) : null}

      <WhyPanel why={res.why} />
    </article>
  );
}
