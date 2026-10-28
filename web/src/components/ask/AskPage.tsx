"use client";

import { ArrowRight, CalendarDays, CheckCircle2, GitBranch, Search, ShieldCheck, Sparkles } from "lucide-react";
import { useId, useState } from "react";
import { useEffect } from "react";
import { RepoSelect } from "@/components/RepoSelect";
import { useRepo } from "@/components/RepoContext";
import { ErrorState, Skeleton, SkeletonLines } from "@/components/states";
import { api, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import type { AskRequest, AskResponse } from "@/lib/types";
import { AnswerCard } from "./AnswerCard";

const EXAMPLES = [
  { label: "Trace a decision", question: "why is app.concurrency set the way it is?", icon: Sparkles },
  { label: "Check what is current", question: "do we still use github.com/lib/pq?", icon: CheckCircle2 },
  { label: "Find the right owner", question: "who should I ask about internal/manager?", icon: GitBranch },
  { label: "See what changed", question: "what changed in docker-compose.yml?", icon: ArrowRight },
  { label: "Try an honest refusal", question: "why does listmonk use MongoDB?", icon: ShieldCheck },
];

interface Turn {
  req: AskRequest;
  res?: AskResponse;
  error?: string;
}

function AnswerSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Asking the graph">
      <div>
        <Skeleton className="h-3 w-40" />
        <Skeleton className="mt-3 h-8 w-3/4" />
      </div>
      <div className="card p-5">
        <SkeletonLines rows={4} />
      </div>
      <div className="flex gap-3 overflow-hidden">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28 w-52 shrink-0" />
        ))}
      </div>
      <div className="card p-4">
        <Skeleton className="h-2.5 w-full" />
        <SkeletonLines rows={2} className="mt-3" />
      </div>
    </div>
  );
}

export function AskPage() {
  const { repo } = useRepo();
  const pulse = useResource(repo ? `pulse-teaser:${repo}` : null, (signal) => api.pulse(repo!, signal));
  const [question, setQuestion] = useState("");
  const [at, setAt] = useState("");
  const [compare, setCompare] = useState(false);
  const [turn, setTurn] = useState<Turn | null>(null);
  const qId = useId();
  const atId = useId();
  const cmpId = useId();
  const busy = turn !== null && !turn.res && !turn.error;

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("question");
    if (!initial) return;
    setQuestion(initial);
    window.history.replaceState({}, "", window.location.pathname);
  }, []);

  const ask = async (q: string) => {
    const text = q.trim();
    if (!text || !repo || busy) return;
    const req: AskRequest = { question: text, repo, at: at ? `${at}T23:59:59Z` : null, mode: compare ? "both" : "graph" };
    setTurn({ req });
    try {
      const res = await api.ask(req);
      setTurn((t) => (t && t.req === req ? { req, res } : t));
    } catch (e) {
      setTurn((t) => (t && t.req === req ? { req, error: errorMessage(e) } : t));
    }
  };

  return (
    <div className="space-y-10">
      <section className="space-y-6">
        <div className="max-w-3xl">
          <p className="eyebrow flex items-center gap-2 text-accent">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
            Repository memory, with receipts
          </p>
          <h1 className="t-display mt-3 max-w-2xl text-[2.35rem] leading-[1.02] text-ink sm:text-[3.5rem]">
            Find the reason behind the code.
          </h1>
          <p className="mt-3 max-w-2xl text-[1rem] leading-relaxed text-ink-2 sm:text-[1.05rem]">
            Ask about a value, dependency, file or module. Untangle follows the repository&apos;s history to surface the decision, the discussion, the
            person and the date — or tell you when the graph has no answer.
          </p>
        </div>

        <form
          className="card relative overflow-hidden p-4 sm:p-5"
          onSubmit={(e) => {
            e.preventDefault();
            void ask(question);
          }}
        >
          <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-accent via-accent/60 to-transparent" aria-hidden />
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow text-ink-3">Ask the repository</p>
              <p className="mt-1 text-[0.85rem] text-ink-2">Start with a question about something you can point to.</p>
            </div>
            <RepoSelect compact />
          </div>

          <div className="mt-4 space-y-3">
          <label htmlFor={qId} className="sr-only">
            Your question
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" aria-hidden />
              <input
                id={qId}
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="why is app.concurrency set the way it is?"
                autoComplete="off"
                enterKeyHint="search"
                className="field pl-9 pr-3 text-[1rem]"
              />
            </div>
            <button type="submit" className="btn btn-primary sm:min-w-28" disabled={busy || !question.trim() || !repo}>
              {busy ? "Asking…" : "Ask"}
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[0.85rem]">
            <label htmlFor={atId} className="inline-flex items-center gap-2 text-ink-2">
              <CalendarDays size={15} className="text-ink-3" aria-hidden />
              <span className="whitespace-nowrap">As of</span>
              <input id={atId} type="date" value={at} max="2099-12-31" onChange={(e) => setAt(e.target.value)} className="field h-9 w-auto py-1 text-[0.85rem]" />
              {at ? (
                <button type="button" className="text-ink-3 underline-offset-4 hover:underline" onClick={() => setAt("")}>
                  clear
                </button>
              ) : null}
            </label>
            <label htmlFor={cmpId} className="inline-flex cursor-pointer select-none items-center gap-2 text-ink-2">
              <input id={cmpId} type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} className="h-4 w-4 accent-[var(--accent)]" />
              Compare with vector-only search
            </label>
          </div>

          <div className="flex flex-wrap gap-1.5" aria-label="Example questions">
            {EXAMPLES.map((ex) => (
              <button
                key={ex.question}
                type="button"
                disabled={busy || !repo}
                onClick={() => {
                  setQuestion(ex.question);
                  void ask(ex.question);
                }}
                className="group inline-flex items-center gap-1.5 rounded-full border border-rule bg-surface px-3 py-1.5 text-[0.8rem] text-ink-2 transition-colors hover:border-accent/50 hover:bg-accent-soft hover:text-ink disabled:opacity-50"
                title={ex.question}
              >
                <ex.icon size={13} aria-hidden className="text-ink-3 transition-colors group-hover:text-accent" />
                {ex.label}
              </button>
            ))}
          </div>
          </div>
          <p className="mt-3 text-[0.75rem] text-ink-3">Tip: ask “why”, “do we still”, “what changed”, or “who should I ask”.</p>
        </form>

        <ol className="grid gap-2 sm:grid-cols-3" aria-label="How Untangle works">
          {[
            { icon: GitBranch, title: "Read the history", body: "Commits, PRs, issues and handover calls become one searchable record." },
            { icon: Sparkles, title: "Find what is in force", body: "Superseded values stay visible while the active decision leads the answer." },
            { icon: ShieldCheck, title: "Show the receipts", body: "Every claim links back to the evidence path the graph actually read." },
          ].map((step, i) => (
            <li key={step.title} className="surface-soft flex gap-3 p-3.5">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent" aria-hidden>
                <step.icon size={15} />
              </span>
              <div>
                <p className="text-[0.82rem] font-semibold text-ink">
                  <span className="t-num mr-1.5 text-ink-3">0{i + 1}</span>
                  {step.title}
                </p>
                <p className="mt-1 text-[0.78rem] leading-relaxed text-ink-2">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
        <p aria-live="polite" className="sr-only">
          {busy ? "Untangle is tracing the repository history." : turn?.res ? "Answer ready." : ""}
        </p>

        {pulse.data?.risks.length ? (
          <section className="surface-soft overflow-hidden" aria-label="Top knowledge risks">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-4 py-3">
              <div><p className="eyebrow text-accent">Pulse noticed</p><p className="mt-1 text-[0.86rem] font-semibold text-ink">{pulse.data.summary.critical ? `${pulse.data.summary.critical} critical knowledge risk${pulse.data.summary.critical === 1 ? "" : "s"}` : "Knowledge risks in this repository"}</p></div>
              <a href="/pulse" className="inline-flex items-center gap-1 text-[0.8rem] font-semibold text-ink-2 underline-offset-4 hover:underline">Open Pulse <ArrowRight size={13} /></a>
            </div>
            <ul className="divide-y divide-rule sm:grid sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              {pulse.data.risks.slice(0, 3).map((risk) => <li key={risk.id}><a href={`/pulse#${risk.id}`} className="block p-3 transition-colors hover:bg-surface"><p className="eyebrow text-ink-3">{risk.category.replaceAll("_", " ")}</p><p className="mt-1 truncate text-[0.86rem] font-semibold text-ink">{risk.entity.name ?? risk.decision.subject}</p><p className="mt-1 line-clamp-2 text-[0.76rem] leading-relaxed text-ink-2">{risk.reasons[0]}</p></a></li>)}
            </ul>
          </section>
        ) : null}
      </section>

      {turn ? (
        <section>
          {turn.error ? (
            <ErrorState title="The question could not be answered" error={turn.error} onRetry={() => void ask(turn.req.question)} />
          ) : turn.res ? (
            <AnswerCard res={turn.res} atIso={turn.req.at} />
          ) : (
            <AnswerSkeleton />
          )}
        </section>
      ) : null}
    </div>
  );
}
