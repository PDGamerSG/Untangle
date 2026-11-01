"use client";

import { CalendarDays, Search } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { RepoSelect } from "@/components/RepoSelect";
import { useRepo } from "@/components/RepoContext";
import { ErrorState, Skeleton, SkeletonLines } from "@/components/states";
import { api, errorMessage } from "@/lib/api";
import { examplesFor } from "@/lib/examples";
import type { AskRequest, AskResponse } from "@/lib/types";
import { AnswerCard } from "./AnswerCard";
import { useStarterQuestions } from "@/components/RepositoryOverview";
import { WaitStatus } from "@/components/WaitStatus";

function examplesOf(repo: string | null) {
  const e = examplesFor(repo);
  return [e.trace, e.current, e.owner, e.changed, e.refusal];
}

interface Turn {
  req: AskRequest;
  res?: AskResponse;
  error?: string;
  comparing?: boolean;
  comparisonError?: string;
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

function AskWorkspace({ repo }: { repo: string | null }) {
  const examples = useStarterQuestions(repo, examplesOf(repo), 5);
  const [question, setQuestion] = useState("");
  const [at, setAt] = useState("");
  const [compare, setCompare] = useState(false);
  const [turn, setTurn] = useState<Turn | null>(null);
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  const qId = useId();
  const atId = useId();
  const cmpId = useId();
  const busy = turn !== null && !turn.res && !turn.error;

  // A question handed over in the URL (from the dashboard, Pulse or an entity page) is asked straight away.
  const [pending, setPending] = useState<string | null>(null);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initial = params.get("question");
    const date = params.get("at");
    if (date && /^\d{4}-\d{2}-\d{2}$/.test(date) && !Number.isNaN(Date.parse(date))
      && new Date(date).toISOString().slice(0, 10) === date) setAt(date);
    if (!initial) return;
    setQuestion(initial);
    setPending(initial);
    window.history.replaceState({}, "", window.location.pathname);
  }, []);

  const ask = async (q: string) => {
    const text = q.trim();
    if (!text || !repo || busy) return;
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    const req: AskRequest = { question: text, repo, at: at ? `${at}T23:59:59Z` : null, mode: compare ? "both" : "graph" };
    setTurn({ req });
    try {
      const res = await api.ask({ ...req, mode: "graph" }, controller.signal);
      if (controller.signal.aborted) return;
      setTurn((t) => (t && t.req === req ? { req, res, comparing: req.mode === "both" } : t));
      if (req.mode === "both") {
        try {
          const comparison = await api.ask({ ...req, mode: "baseline" }, controller.signal);
          if (controller.signal.aborted) return;
          setTurn(t => t?.req === req ? { req, res: { ...res, mode: "both", baseline: comparison.baseline } } : t);
        } catch (e) {
          if (controller.signal.aborted) return;
          setTurn(t => t?.req === req ? { req, res, comparisonError: errorMessage(e) } : t);
        }
      }
    } catch (e) {
      if (controller.signal.aborted) return;
      setTurn((t) => (t && t.req === req ? { req, error: errorMessage(e) } : t));
    }
  };

  useEffect(() => {
    if (!pending || !repo) return;
    setPending(null);
    void ask(pending);
    // `ask` reads the current repo and options; it only needs to run once per handed-over question.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending, repo]);

  return (
    <div className="space-y-10">
      <section className="space-y-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-3xl">
            <h1 className="t-display max-w-2xl text-[2.2rem] leading-[1.04] text-ink sm:text-[2.8rem]">Find the reason behind the code.</h1>
            <p className="mt-2 max-w-2xl text-[0.98rem] leading-relaxed text-ink-2">
              Ask about a value, dependency, file or module. Untangle follows the repository&apos;s history to the decision, the discussion, the
              person and the date, or says plainly when the graph has no answer.
            </p>
          </div>
          <RepoSelect compact />
        </header>

        <form
          className="card p-4 sm:p-5"
          onSubmit={(e) => {
            e.preventDefault();
            void ask(question);
          }}
        >
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
                placeholder={examples[0]}
                autoComplete="off"
                enterKeyHint="search"
                className="field pl-9 pr-3 text-[1rem]"
              />
            </div>
            <button type="submit" className="btn btn-primary sm:min-w-24" disabled={busy || !question.trim() || !repo}>
              {busy ? "Asking…" : "Ask"}
            </button>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[0.85rem]">
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

          <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-rule pt-4 text-[0.82rem] text-ink-3" aria-label="Example questions">
            <span className="mr-0.5">Try</span>
            {examples.map((q) => (
              <button
                key={q}
                type="button"
                disabled={busy || !repo}
                onClick={() => {
                  setQuestion(q);
                  void ask(q);
                }}
                className="example"
              >
                {q}
              </button>
            ))}
          </div>
        </form>

        <p aria-live="polite" className="sr-only">
          {busy ? "Untangle is tracing the repository history." : turn?.res ? "Answer ready." : ""}
        </p>
      </section>

      {turn ? (
        <section>
          {turn.error ? (
            <ErrorState title="The question could not be answered" error={turn.error} onRetry={() => void ask(turn.req.question)} />
          ) : turn.res ? (
            <div className="space-y-5">
              {turn.comparing ? <WaitStatus key="comparison" label="Preparing the optional search comparison. Your cited answer is ready below." min={10} max={45}
                cancelLabel="Cancel comparison" onCancel={() => { active.current?.abort(); setTurn(t => t ? { ...t, comparing: false } : t); }} /> : null}
              {turn.comparisonError ? <p role="status" className="card-muted p-4 text-[0.85rem]">Comparison unavailable: {turn.comparisonError} Your graph answer is still available.</p> : null}
              <AnswerCard res={turn.res} atIso={turn.req.at} />
            </div>
          ) : (
            <div className="space-y-5"><WaitStatus key="answer" label="Finding repository evidence and preparing your answer." cancelLabel="Cancel answer"
              onCancel={() => { active.current?.abort(); setTurn(null); }} /><AnswerSkeleton /></div>
          )}
        </section>
      ) : null}
    </div>
  );
}

export function AskPage() {
  const { repo, loading, error, reload } = useRepo();
  if (error) return <ErrorState title="Could not load repositories" error={error} onRetry={reload} />;
  if (loading) return <WaitStatus label="Loading repositories." min={1} max={5} />;
  if (!repo) return <div className="card p-5">Add a public GitHub repository from <a href="/repositories" className="text-accent underline">Repositories</a> to ask about its code.</div>;
  return <AskWorkspace key={repo} repo={repo} />;
}
