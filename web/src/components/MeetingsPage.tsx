"use client";

import Link from "next/link";
import { AudioLines, Mic } from "lucide-react";
import { RepoSelect } from "./RepoSelect";
import { useRepo } from "./RepoContext";
import { EmptyState, ErrorState, Skeleton, SkeletonLines } from "./states";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDateTime, fmtDuration } from "@/lib/format";
import { MeetingUpload } from "./MeetingUpload";

export function NotConfigured() {
  return (
    <div className="card-muted p-6">
      <p className="flex items-center gap-2 font-semibold text-ink">
        <Mic size={16} className="text-ink-3" /> KT ingestion not configured
      </p>
      <p className="mt-2 max-w-xl text-[0.9rem] leading-relaxed text-ink-2">
        The API answered <code className="t-code">501</code>: handover-call ingestion is switched off on this server. Set{" "}
        <code className="t-code">SARVAM_API_KEY</code> and run <code className="t-code">untangle kt ingest --repo owner/name --audio call.mp3</code> (or{" "}
        <code className="t-code">--transcript call.json</code>) to add a meeting. Everything else works without it.
      </p>
    </div>
  );
}

export function MeetingsPage() {
  const { repo } = useRepo();
  const res = useResource(repo ? `meetings:${repo}` : null, (signal) => api.meetings(repo!, signal));

  return (
    <div className="space-y-7">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="t-display text-[2.1rem] leading-[1.05] text-ink sm:text-[2.4rem]">Handover calls</h1>
          <p className="mt-2 max-w-2xl text-[0.95rem] text-ink-2">
            Knowledge-transfer recordings, transcribed in the language they were spoken, with the decisions Untangle pulled out of them linked to the code
            they are about.
          </p>
        </div>
        <RepoSelect compact />
      </header>

      <MeetingUpload repo={repo} onUploaded={res.reload} />

      {res.loading ? (
        <ul className="grid gap-3 sm:grid-cols-2" role="status" aria-label="Loading meetings">
          {[0, 1].map((i) => (
            <li key={i} className="card p-4">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="mt-2 h-3 w-1/2" />
              <SkeletonLines rows={2} className="mt-4" />
            </li>
          ))}
        </ul>
      ) : res.error ? (
        res.errorStatus === 501 ? (
          <NotConfigured />
        ) : (
          <ErrorState title="Could not load meetings" error={res.error} onRetry={res.reload} />
        )
      ) : !res.data?.length ? (
        <EmptyState title="No handover calls for this repository yet">
          Add a recording or transcript above to make this repository’s handovers searchable.
        </EmptyState>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {res.data.map((m) => (
            <li key={m.id}>
              <Link href={`/meetings/${encodeURIComponent(m.id)}`} className="card block h-full p-4 transition-colors hover:border-rule-strong">
                <p className="flex items-center gap-2 text-[0.76rem] font-semibold uppercase tracking-wider text-ink-3">
                  {m.audio_uri ? <AudioLines size={14} aria-hidden /> : <Mic size={14} aria-hidden />}
                  {m.language} · {m.source}
                </p>
                <h2 className="t-display mt-1.5 text-[1.3rem] text-ink">{m.title}</h2>
                <p className="t-num mt-1 text-[0.82rem] text-ink-3">
                  {fmtDateTime(m.started_at_iso)} · {fmtDuration(m.duration_ms)}
                </p>
                {m.summary ? <p className="mt-2 line-clamp-3 text-[0.88rem] leading-relaxed text-ink-2">{m.summary}</p> : null}
                <p className="t-num mt-3 text-[0.8rem] text-ink-3">
                  {m.utterance_count} utterances · {m.decision_count} {m.decision_count === 1 ? "decision" : "decisions"} extracted
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
