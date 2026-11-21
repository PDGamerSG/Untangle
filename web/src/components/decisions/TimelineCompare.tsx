"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { InlineCode } from "@/components/ask/AnswerText";
import { ErrorState, SkeletonLines } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDay } from "@/lib/format";
import type { DecisionCard } from "@/lib/types";

function More({ shown, total }: { shown: number; total: number }) {
  return total > shown ? <p className="px-4 pb-2 text-[0.8rem] text-ink-3">Newest {shown} of {total} shown.</p> : null;
}

function DecisionLink({ d, superseded = false }: { d: DecisionCard; superseded?: boolean }) {
  return (
    <Link href={`/decisions/${encodeURIComponent(d.id)}`} className={`underline-offset-4 hover:underline ${superseded ? "mark-superseded" : "text-ink"}`}>
      <InlineCode text={d.text} />
    </Link>
  );
}

/** "What changed between two dates": values replaced, decisions that took effect and decisions that stopped. The
 * server compares every decision in force on both dates, so the counts are exact even for large repositories. */
export function TimelineCompare({ repo, day, minDay, todayDay }: { repo: string; day: string; minDay: string; todayDay: string }) {
  const [other, setOther] = useState("");
  const inputId = useId();
  const [from, to] = other && other < day ? [other, day] : [day, other];
  const diff = useResource(other ? `timeline-diff:${repo}:${from}:${to}` : null, (signal) => api.timelineCompare(repo, from, to, signal));
  const d = diff.data;
  const total = d ? d.counts.changed + d.counts.started + d.counts.ended : 0;

  return (
    <section aria-label="Compare two dates" className="card">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <label htmlFor={inputId} className="text-[0.9rem] font-semibold text-ink">
          Compare {fmtDay(day)} with
        </label>
        <div className="flex items-center gap-2">
          <input id={inputId} type="date" min={minDay} max={todayDay} value={other} onChange={(e) => setOther(e.target.value && e.target.value !== day ? e.target.value : "")}
            className="field h-9 w-auto py-1 text-[0.85rem]" />
          {other ? <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOther("")}>Clear</button> : null}
        </div>
      </div>
      {!other ? null : diff.error ? (
        <div className="px-4 pb-4"><ErrorState title="Could not compare the dates" error={diff.error} onRetry={diff.reload} /></div>
      ) : !d ? (
        <div className="px-4 pb-4"><SkeletonLines rows={3} /></div>
      ) : (
        <div className="border-t border-rule">
          <p className="px-4 py-2.5 text-[0.88rem] text-ink-2" aria-live="polite">
            {total ? <>Between {fmtDay(from)} and {fmtDay(to)}: {d.counts.changed} changed, {d.counts.started} started, {d.counts.ended} ended.</>
              : <>Nothing changed between {fmtDay(from)} and {fmtDay(to)}.</>}
          </p>
          {d.changed.length ? (
            <div className="border-t border-rule">
              <p className="px-4 pt-2.5 text-[0.8rem] font-semibold text-ink-3">Changed</p>
              <ul className="divide-y divide-rule">
                {d.changed.map((c) => (
                  <li key={c.after.id} className="break-words px-4 py-2 text-[0.87rem]">
                    <span className="font-semibold text-ink">{c.after.subject}</span>{" "}
                    <span className="t-code mark-superseded">{c.before.object}</span> →{" "}
                    <Link href={`/decisions/${encodeURIComponent(c.after.id)}`} className="t-code text-ink underline-offset-4 hover:underline">{c.after.object}</Link>
                    <span className="t-num ml-2 text-[0.78rem] text-ink-3">{fmtDay(c.after.valid_from_iso)}</span>
                  </li>
                ))}
              </ul>
              <More shown={d.changed.length} total={d.counts.changed} />
            </div>
          ) : null}
          {d.started.length ? (
            <div className="border-t border-rule">
              <p className="px-4 pt-2.5 text-[0.8rem] font-semibold text-ink-3">Started</p>
              <ul className="divide-y divide-rule">
                {d.started.map((s) => (
                  <li key={s.id} className="px-4 py-2 text-[0.87rem]"><DecisionLink d={s} /><span className="t-num ml-2 text-[0.78rem] text-ink-3">{fmtDay(s.valid_from_iso)}</span></li>
                ))}
              </ul>
              <More shown={d.started.length} total={d.counts.started} />
            </div>
          ) : null}
          {d.ended.length ? (
            <div className="border-t border-rule">
              <p className="px-4 pt-2.5 text-[0.8rem] font-semibold text-ink-3">Ended</p>
              <ul className="divide-y divide-rule">
                {d.ended.map((e) => <li key={e.id} className="px-4 py-2 text-[0.87rem]"><DecisionLink d={e} superseded /></li>)}
              </ul>
              <More shown={d.ended.length} total={d.counts.ended} />
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
