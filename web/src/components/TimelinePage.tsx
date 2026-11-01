"use client";

import { useId, useState } from "react";
import { DecisionWorkbench } from "./DecisionWorkbench";
import { RepoSelect } from "./RepoSelect";
import { useRepo } from "./RepoContext";
import { EmptyState, ErrorState, Skeleton, SkeletonLines } from "./states";
import { api } from "@/lib/api";
import { primeResource, useDebounced, useResource } from "@/lib/hooks";
import { fmtDay } from "@/lib/format";

const DAY_MS = 86_400_000;

function dayOf(iso: string): string {
  return iso.slice(0, 10);
}

/** The slider spans the repository's first decision to today. The API reports the first decision date
 * (`earliest_iso`); older fixtures without it fall back to the earliest date among the decisions returned. */
function useBounds(repo: string | null) {
  return useResource(repo ? `timeline-bounds:${repo}` : null, async (signal) => {
    const today = new Date();
    const todayDay = dayOf(today.toISOString());
    const now = await api.timeline(repo!, `${todayDay}T23:59:59Z`, signal);
    // The page's first view is today, so this response is the one it will ask for next.
    primeResource(`timeline:${repo}:${todayDay}`, now);
    let minMs = now.earliest_iso ? Date.parse(now.earliest_iso) : NaN;
    if (Number.isNaN(minMs)) {
      const dates = [...now.active, ...now.superseded_since].map((d) => Date.parse(d.valid_from_iso)).filter((n) => !Number.isNaN(n));
      minMs = dates.length ? Math.min(...dates) : today.getTime() - 365 * DAY_MS;
    }
    return { minDay: dayOf(new Date(minMs).toISOString()), todayDay };
  });
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
            Explore the decisions in force on any date. Filter by code, reason or person, inspect the sources, and take the evidence into your next handover.
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
      ) : repo && timeline.data ? (
        <DecisionWorkbench key={`${repo}:${timeline.data.at_iso}`} repo={repo} snapshot={timeline.data} />
      ) : repo ? (
        <div className="card p-5" role="status" aria-label="Loading decisions"><Skeleton className="h-7 w-48" /><SkeletonLines rows={5} className="mt-5" /></div>
      ) : <EmptyState title="Choose an ingested repository to explore decisions" />}
    </div>
  );
}
