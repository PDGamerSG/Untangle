"use client";

import Link from "next/link";
import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { externalHref } from "@/lib/api";
import { fmtDay, signalLabel } from "@/lib/format";
import type { DecisionCard } from "@/lib/types";
import { InlineCode } from "@/components/ask/AnswerText";

const STEP_MS = 3200;

/**
 * Steps through one decision's history, oldest first: what the value was, when and where it changed, who stated it
 * and the reason recorded at each step. Arrow keys move between steps; Play advances on its own and stops at the end.
 */
export function DecisionReplay({ chain, currentId }: { chain: DecisionCard[]; currentId: string }) {
  const start = Math.max(0, chain.findIndex((d) => d.id === currentId));
  const [index, setIndex] = useState(start);
  const [playing, setPlaying] = useState(false);
  const headingId = useId();

  useEffect(() => {
    if (!playing || index >= chain.length - 1) return;
    const timer = window.setTimeout(() => {
      const next = Math.min(chain.length - 1, index + 1);
      setIndex(next);
      if (next >= chain.length - 1) setPlaying(false);
    }, STEP_MS);
    return () => window.clearTimeout(timer);
  }, [playing, index, chain.length]);

  if (chain.length < 2) return null;
  const d = chain[index];
  const prev = index > 0 ? chain[index - 1] : null;
  const source = d.decided_in;
  const sourceHref = externalHref(source?.url);
  const go = (i: number) => setIndex(Math.max(0, Math.min(chain.length - 1, i)));

  return (
    <section
      aria-labelledby={headingId}
      className="card p-4 sm:p-5"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") { e.preventDefault(); setPlaying(false); go(index + 1); }
        if (e.key === "ArrowLeft") { e.preventDefault(); setPlaying(false); go(index - 1); }
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={headingId} className="text-[0.95rem] font-semibold text-ink">Replay this decision</h2>
        <div className="flex items-center gap-1">
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setPlaying(false); go(index - 1); }} disabled={index === 0} aria-label="Previous step">
            <ChevronLeft size={15} aria-hidden />
          </button>
          <span className="t-num min-w-16 text-center text-[0.8rem] text-ink-3" aria-live="polite">Step {index + 1} of {chain.length}</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setPlaying(false); go(index + 1); }} disabled={index === chain.length - 1} aria-label="Next step">
            <ChevronRight size={15} aria-hidden />
          </button>
          <button
            type="button"
            className="btn btn-line btn-sm ml-1"
            onClick={() => {
              if (playing) setPlaying(false);
              else {
                if (index >= chain.length - 1) setIndex(0);
                setPlaying(true);
              }
            }}
          >
            {playing ? <Pause size={14} aria-hidden /> : <Play size={14} aria-hidden />}
            {playing ? "Pause" : index >= chain.length - 1 ? "Replay" : "Play"}
          </button>
        </div>
      </div>

      <ol className="mt-4 flex items-start gap-0 overflow-x-auto pb-1" aria-label="Steps">
        {chain.map((c, i) => (
          <li key={c.id} className="flex min-w-[5.5rem] flex-1 flex-col items-center">
            <button
              type="button"
              onClick={() => { setPlaying(false); go(i); }}
              aria-current={i === index ? "step" : undefined}
              aria-label={`${fmtDay(c.valid_from_iso)}: ${c.object}`}
              className="group flex w-full flex-col items-center gap-1"
            >
              <span className="flex w-full items-center">
                <span className={`h-px flex-1 ${i === 0 ? "bg-transparent" : i <= index ? "bg-accent" : "bg-rule-strong"}`} />
                <span className={`h-3 w-3 shrink-0 rounded-full border-2 ${i === index ? "border-accent bg-accent ring-4 ring-accent/20" : i < index ? "border-accent bg-surface" : "border-rule-strong bg-surface"}`} />
                <span className={`h-px flex-1 ${i === chain.length - 1 ? "bg-transparent" : i < index ? "bg-accent" : "bg-rule-strong"}`} />
              </span>
              <span className={`t-num text-[0.72rem] ${i === index ? "font-semibold text-ink" : "text-ink-3 group-hover:text-ink-2"}`}>{fmtDay(c.valid_from_iso)}</span>
            </button>
          </li>
        ))}
      </ol>

      <div className="mt-4 border-t border-rule pt-4">
        <p className="text-[0.8rem] text-ink-3">
          {d.valid_to_iso ? `${fmtDay(d.valid_from_iso)} → ${fmtDay(d.valid_to_iso)}` : `Since ${fmtDay(d.valid_from_iso)}, in force today`}
          {" · "}{signalLabel(d.signal)}
        </p>
        <p className={`t-display mt-1 break-words text-[1.6rem] leading-tight ${d.status === "active" ? "text-ink" : "mark-superseded"}`}>{d.object}</p>
        {prev ? (
          <p className="mt-1 text-[0.86rem] text-ink-2">
            Changed from <span className="t-code">{prev.object}</span>
          </p>
        ) : (
          <p className="mt-1 text-[0.86rem] text-ink-2">The first recorded value.</p>
        )}
        <p className="mt-2 text-[0.92rem] leading-relaxed text-ink"><InlineCode text={d.text} /></p>
        {d.rationale ? <p className="mt-2 border-l-2 border-rule-strong pl-3 text-[0.88rem] italic text-ink-2">{d.rationale}</p> : <p className="mt-2 text-[0.82rem] text-ink-3">No reason recorded for this step.</p>}
        <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[0.82rem]">
          {d.stated_by ? <span className="text-ink-2">Stated by <span className="font-semibold text-ink">{d.stated_by.name}</span></span> : null}
          {source ? (
            sourceHref ? (
              <a href={sourceHref} target="_blank" rel="noreferrer" className="font-semibold text-accent underline-offset-4 hover:underline">{source.title}</a>
            ) : (
              <span className="text-ink-2">{source.title}</span>
            )
          ) : null}
          {d.id !== currentId ? <Link href={`/decisions/${encodeURIComponent(d.id)}`} className="font-semibold text-ink-2 underline-offset-4 hover:underline">Open this step</Link> : null}
        </p>
      </div>
    </section>
  );
}
