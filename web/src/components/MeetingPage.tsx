"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Play } from "lucide-react";
import { useEffect, useRef } from "react";
import { EntityChip } from "./Chip";
import { DecisionCard } from "./DecisionCard";
import { NotConfigured } from "./MeetingsPage";
import { EmptyState, ErrorState, SectionTitle, Skeleton, SkeletonLines } from "./states";
import { api, API_BASE, SAMPLE_MODE } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDateTime, fmtDuration, fmtOffset } from "@/lib/format";
import type { MeetingDetail } from "@/lib/types";

function audioSrc(uri: string): string {
  if (/^https?:\/\//i.test(uri) || SAMPLE_MODE) return uri;
  return uri.startsWith("/") ? `${API_BASE}${uri}` : uri;
}

const SPEAKER_TONES = ["var(--k-pr)", "var(--k-commit)", "var(--k-utterance)", "var(--k-document)", "var(--k-config)"];

function Transcript({ m }: { m: MeetingDetail }) {
  const audio = useRef<HTMLAudioElement>(null);
  const speakerIndex = new Map(m.speakers.map((s, i) => [s.label, i]));
  const nameOf = (label: string) => m.speakers.find((s) => s.label === label)?.person?.name ?? label;

  useEffect(() => {
    // Scroll to the utterance named in the URL hash once the transcript has rendered.
    const hash = window.location.hash;
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: "center" });
  }, [m.id]);

  const playFrom = (ms: number) => {
    const el = audio.current;
    if (!el) return;
    el.currentTime = ms / 1000;
    void el.play();
  };

  return (
    <>
      {m.audio_uri ? (
        <div className="sticky top-[5.3rem] z-30 sm:top-14 lg:top-0 -mx-4 border-b border-rule bg-bg/90 px-4 py-2 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-10 lg:px-10">
          <audio ref={audio} controls preload="metadata" src={audioSrc(m.audio_uri)} className="w-full" aria-label={`Recording of ${m.title}`} />
        </div>
      ) : null}

      {m.speakers.length ? (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[0.82rem] text-ink-2" aria-label="Speakers">
          {m.speakers.map((s, i) => (
            <li key={s.label} className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: SPEAKER_TONES[i % SPEAKER_TONES.length] }} aria-hidden />
              <span className="font-semibold text-ink">{s.person?.name ?? s.label}</span>
              {s.person ? <span className="t-code text-ink-3">{s.label}</span> : <span className="text-ink-3">(unidentified)</span>}
            </li>
          ))}
        </ul>
      ) : null}

      <ol className="space-y-1" aria-label="Transcript">
        {m.utterances.map((u) => {
          const idx = speakerIndex.get(u.speaker_label) ?? 0;
          return (
            <li
              key={u.id}
              id={`utt-${u.seq}`}
              className="group grid scroll-mt-32 gap-x-3 gap-y-1 rounded-lg px-2 py-2.5 target:bg-accent-soft sm:grid-cols-[7.5rem_1fr]"
            >
              <div className="flex items-center gap-2 sm:flex-col sm:items-start sm:gap-1">
                <span className="inline-flex items-center gap-1.5 text-[0.8rem] font-semibold text-ink">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: SPEAKER_TONES[idx % SPEAKER_TONES.length] }} aria-hidden />
                  {nameOf(u.speaker_label)}
                </span>
                <span className="t-num text-[0.76rem] text-ink-3">
                  {fmtOffset(u.start_ms)}–{fmtOffset(u.end_ms)}
                </span>
                {m.audio_uri ? (
                  <button
                    type="button"
                    onClick={() => playFrom(u.start_ms)}
                    className="btn btn-ghost btn-sm -ml-1 h-7 px-1.5 text-[0.74rem] text-ink-3 sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100"
                    aria-label={`Play from ${fmtOffset(u.start_ms)}`}
                  >
                    <Play size={12} /> play from here
                  </button>
                ) : null}
              </div>
              <div className="min-w-0">
                <p className="text-[1.02rem] leading-relaxed text-ink">{u.text_en || u.text}</p>
                {u.mentions?.length ? (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {u.mentions.map((e) => (
                      <EntityChip key={e.id} entity={e} />
                    ))}
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </>
  );
}

export function MeetingPage() {
  const params = useParams<{ id: string }>();
  const id = (() => {
    try {
      return decodeURIComponent(params.id ?? "");
    } catch {
      return params.id ?? "";
    }
  })();
  const res = useResource(id ? `meeting:${id}` : null, (signal) => api.meeting(id, signal));

  if (res.loading)
    return (
      <div className="space-y-6" role="status" aria-label="Loading meeting">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="h-12 w-full" />
        <SkeletonLines rows={6} />
      </div>
    );
  if (res.error) {
    if (res.errorStatus === 501) return <NotConfigured />;
    if (res.errorStatus === 404)
      return (
        <EmptyState title="No such meeting">
          <code className="t-code">{id}</code> is not in the graph.{" "}
          <Link href="/meetings" className="underline">
            All meetings
          </Link>
        </EmptyState>
      );
    return <ErrorState title="Could not load the meeting" error={res.error} onRetry={res.reload} />;
  }
  const m = res.data;
  if (!m) return null;

  return (
    <div className="space-y-6">
      <nav aria-label="Breadcrumb" className="text-[0.82rem] text-ink-3">
        <Link href="/meetings" className="hover:underline">
          Meetings
        </Link>{" "}
        / <span className="text-ink-2">{m.title}</span>
      </nav>
      <header>
        <p className="text-[0.76rem] font-semibold uppercase tracking-wider text-ink-3">
          {m.language} · {m.source}
        </p>
        <h1 className="t-display mt-1 text-[1.9rem] leading-[1.1] text-ink sm:text-[2.3rem]">{m.title}</h1>
        <p className="t-num mt-2 text-[0.85rem] text-ink-3">
          {fmtDateTime(m.started_at_iso)} · {fmtDuration(m.duration_ms)} · {m.utterances.length} utterances
        </p>
        {m.summary ? <p className="mt-3 max-w-3xl text-[0.95rem] leading-relaxed text-ink-2">{m.summary}</p> : null}
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="space-y-4" aria-label="Recording and transcript">
          <Transcript m={m} />
        </section>
        <aside className="lg:sticky lg:top-16 lg:self-start">
          <SectionTitle hint={`${m.decisions.length}`}>Decisions from this call</SectionTitle>
          {m.decisions.length ? (
            <ul className="space-y-3">
              {m.decisions.map((d) => (
                <li key={d.id}>
                  <DecisionCard decision={d} />
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No decisions extracted" />
          )}
        </aside>
      </div>
    </div>
  );
}
