import { KindTag } from "@/components/Chip";
import { SectionTitle } from "@/components/states";
import { AnswerText } from "./AnswerText";
import { normaliseKind, KIND_LABEL } from "@/lib/format";
import type { AskResponse } from "@/lib/types";

export function BaselineCompare({ res }: { res: AskResponse }) {
  const b = res.baseline;
  if (!b) return null;
  return (
    <section aria-label="Graph answer compared with vector-only search">
      <SectionTitle hint="same question, two retrieval methods">Graph vs vector-only</SectionTitle>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="card border-accent/40 p-4">
          <p className="text-[0.85rem] font-semibold text-accent">Graph answer</p>
          <AnswerText text={res.answer} citations={res.citations} className="mt-2 text-[0.92rem] leading-relaxed text-ink" />
          <p className="t-num mt-3 text-[0.78rem] text-ink-3">
            {res.refused ? "Refused: nothing anchored in the graph." : `Confidence ${Math.round(res.confidence.score * 100)}% (${res.confidence.label}) · ${res.supersession.length ? `${res.supersession.length} supersession${res.supersession.length === 1 ? "" : "s"} applied` : "no supersession"}`}
          </p>
        </div>
        <div className="card-muted p-4">
          <p className="text-[0.85rem] font-semibold text-ink-3">Vector-only answer</p>
          <p className="mt-2 whitespace-pre-line text-[0.92rem] leading-relaxed text-ink-2">{b.answer}</p>
          <p className="mt-3 text-[0.78rem] italic text-ink-3">{b.note}</p>
          {b.chunks.length ? (
            <ol className="mt-3 space-y-1.5">
              {b.chunks.map((c) => {
                const kind = normaliseKind(c.source_kind, c.id);
                return (
                  <li key={c.id} className="rounded-md border border-rule bg-surface px-2.5 py-2 text-[0.8rem]">
                    <p className="flex items-center justify-between gap-2">
                      <KindTag kind={kind}>
                        <span className="chip-kind">{KIND_LABEL[kind]}</span>
                      </KindTag>
                      <span className="t-num text-ink-3">cosine {c.score.toFixed(2)}</span>
                    </p>
                    <p className="mt-1 line-clamp-3 text-ink-2">{c.text}</p>
                  </li>
                );
              })}
            </ol>
          ) : null}
        </div>
      </div>
    </section>
  );
}
