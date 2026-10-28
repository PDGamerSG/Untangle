"use client";

import { useId, useState } from "react";
import { DecisionCard } from "./DecisionCard";
import { RepoSelect } from "./RepoSelect";
import { useRepo } from "./RepoContext";
import { EmptyState, ErrorState, SectionTitle, Skeleton, SkeletonLines } from "./states";
import { api } from "@/lib/api";
import { useDebounced, useResource } from "@/lib/hooks";
import { fmtDay } from "@/lib/format";
import type { DecisionCard as DecisionCardT } from "@/lib/types";

const DAY_MS = 86_400_000;

function dayOf(iso: string): string {
  return iso.slice(0, 10);
}

/** The slider spans the repository's first decision to today. The API reports the first decision date
 * (`earliest_iso`); older fixtures without it fall back to the earliest date among the decisions returned. */
function useBounds(repo: string | null) {
  return useResource(repo ? `timeline-bounds:${repo}` : null, async (signal) => {
    const today = new Date();
    const now = await api.timeline(repo!, today.toISOString(), signal);
    let minMs = now.earliest_iso ? Date.parse(now.earliest_iso) : NaN;
    if (Number.isNaN(minMs)) {
      const dates = [...now.active, ...now.superseded_since].map((d) => Date.parse(d.valid_from_iso)).filter((n) => !Number.isNaN(n));
      minMs = dates.length ? Math.min(...dates) : today.getTime() - 365 * DAY_MS;
    }
    return { minDay: dayOf(new Date(minMs).toISOString()), todayDay: dayOf(today.toISOString()) };
  });
}

function Column({ title, hint, items, muted, empty, loading }: { title: string; hint?: string; items?: DecisionCardT[]; muted: boolean; empty: string; loading: boolean }) {
  return (
    <section aria-label={title} className="min-w-0">
      <SectionTitle hint={loading ? undefined : hint}>{title}</SectionTitle>
      {loading ? (
        <div className="space-y-3" role="status" aria-label="Loading">
          {[0, 1].map((i) => (
            <div key={i} className="card p-4">
              <Skeleton className="h-3 w-32" />
              <Skeleton className="mt-3 h-6 w-1/3" />
              <SkeletonLines rows={2} className="mt-3" />
            </div>
          ))}
        </div>
      ) : items && items.length ? (
        <ul className="space-y-3">
          {items.map((d) => (
            <li key={d.id}>
              <DecisionCard decision={d} muted={muted} />
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title={empty} />
      )}
    </section>
  );
}

export function TimelinePage() {
  const { repo } = useRepo();
  const bounds = useBounds(repo);
  const [atDay, setAtDay] = useState<string | null>(null); // null = today
  const debouncedDay = useDebounced(atDay, 250);
  const sliderId = useId();
  const dateId = useId();

  const effectiveDay = debouncedDay ?? bounds.data?.todayDay ?? null;
  const timeline = useResource(repo && effectiveDay ? `timeline:${repo}:${effectiveDay}` : null, (signal) => api.timeline(repo!, `${effectiveDay}T23:59:59Z`, signal));

  const minDay = bounds.data?.minDay ?? null;
  const todayDay = bounds.data?.todayDay ?? null;
  const shownDay = atDay ?? todayDay;
  const days = minDay && todayDay ? Math.max(1, Math.round((Date.parse(todayDay) - Date.parse(minDay)) / DAY_MS)) : 0;
  const offset = minDay && shownDay ? Math.max(0, Math.min(days, Math.round((Date.parse(shownDay) - Date.parse(minDay)) / DAY_MS))) : days;

  return (
    <div className="space-y-7">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="t-display text-[2.1rem] leading-[1.05] text-ink sm:text-[2.4rem]">What was true, when</h1>
          <p className="mt-2 max-w-2xl text-[0.95rem] text-ink-2">
            Slide to any date and see the decisions in force then, and which of them have since been replaced. Belief at a date comes from{" "}
            <code className="t-code">valid_from ≤ t &lt; valid_to</code> on every decision.
          </p>
        </div>
        <RepoSelect compact />
      </header>

      <section className="card p-4" aria-label="Date">
        {bounds.loading ? (
          <div className="space-y-3" role="status" aria-label="Loading date range">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-5 w-full" />
          </div>
        ) : bounds.error ? (
          <ErrorState title="Could not load the timeline range" error={bounds.error} onRetry={bounds.reload} />
        ) : minDay && todayDay ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-[0.95rem] text-ink-2">
                In force on <span className="t-display text-[1.5rem] text-ink">{fmtDay(shownDay)}</span>
                {atDay === null ? <span className="ml-2 text-[0.8rem] text-ink-3">(today)</span> : null}
              </p>
              <div className="flex items-center gap-2 text-[0.85rem]">
                <label htmlFor={dateId} className="text-ink-3">
                  Jump to
                </label>
                <input
                  id={dateId}
                  type="date"
                  className="field h-9 w-auto py-1 text-[0.85rem]"
                  min={minDay}
                  max={todayDay}
                  value={shownDay ?? ""}
                  onChange={(e) => setAtDay(e.target.value && e.target.value !== todayDay ? e.target.value : null)}
                />
                {atDay !== null ? (
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAtDay(null)}>
                    Today
                  </button>
                ) : null}
              </div>
            </div>
            <label htmlFor={sliderId} className="sr-only">
              Date slider
            </label>
            <input
              id={sliderId}
              type="range"
              className="slider mt-3"
              min={0}
              max={days}
              step={1}
              value={offset}
              aria-valuetext={fmtDay(shownDay)}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (v >= days) setAtDay(null);
                else setAtDay(dayOf(new Date(Date.parse(minDay) + v * DAY_MS).toISOString()));
              }}
            />
            <div className="t-num mt-1 flex justify-between text-[0.76rem] text-ink-3">
              <span>{fmtDay(minDay)}</span>
              <span>today</span>
            </div>
          </>
        ) : null}
      </section>

      {timeline.error ? (
        <ErrorState title="Could not load the timeline" error={timeline.error} onRetry={timeline.reload} />
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <Column
            title={`In force on ${shownDay ? fmtDay(shownDay) : "…"}`}
            hint={timeline.data ? `${timeline.data.active.length} active` : undefined}
            items={timeline.data?.active}
            muted={false}
            empty="No decisions were in force on this date."
            loading={timeline.loading || (!timeline.data && !timeline.error)}
          />
          <Column
            title="Superseded since then"
            hint={timeline.data ? `${timeline.data.superseded_since.length} replaced` : undefined}
            items={timeline.data?.superseded_since}
            muted
            empty={atDay === null ? "Nothing is superseded after today." : "Nothing in force on this date has been replaced since."}
            loading={timeline.loading || (!timeline.data && !timeline.error)}
          />
        </div>
      )}
    </div>
  );
}
