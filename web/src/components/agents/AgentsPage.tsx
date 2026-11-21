"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { ArrowUp, Bot, KeyRound, LoaderCircle, Trash2 } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import { CopyButton } from "@/components/ui/CopyButton";
import { EmptyState, ErrorState, SectionTitle, SkeletonLines } from "@/components/ui/states";
import { RepoSelect } from "@/components/repositories/RepoSelect";
import { useRepo } from "@/components/repositories/RepoContext";
import { NoRepository } from "@/components/repositories/NoRepository";
import { api, API_BASE, errorMessage, externalHref } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDay } from "@/lib/format";
import type { AgentChatTurn, AgentToken } from "@/lib/types";

const STARTERS = [
  "What changed most recently, and why?",
  "Who knows the most about the configuration?",
  "Which dependencies have a recorded reason?",
];

const TOOL_LABEL: Record<string, string> = {
  ask_why: "Asked why",
  list_decisions: "Listed decisions",
  decision_timeline: "Checked the timeline",
  who_to_ask: "Found people",
  search_repository: "Searched",
  recall_agent_notes: "Read agent notes",
  list_repositories: "Listed repositories",
};

/** The built-in agent: answers here with the deployment's model and Untangle's read-only tools. No token needed. */
function BuiltInAgent() {
  const { repo } = useRepo();
  const [turns, setTurns] = useState<AgentChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputId = useId();
  const endRef = useRef<HTMLDivElement>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [turns, busy]);

  async function send(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    const next: AgentChatTurn[] = [...turns, { role: "user", content: text }];
    setTurns(next);
    setDraft("");
    setError(null);
    setBusy(true);
    controller.current = new AbortController();
    try {
      const result = await api.agentChat(
        { repo, messages: next.map(({ role, content }) => ({ role, content })) },
        controller.current.signal,
      );
      setTurns([...next, { role: "assistant", content: result.reply, steps: result.steps }]);
    } catch (e) {
      setError(errorMessage(e));
      setTurns(turns);
      setDraft(text);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-4" aria-labelledby="agent-chat-heading">
      <SectionTitle hint={repo ? `Reading ${repo}` : "No repository selected"}>
        <span id="agent-chat-heading">Ask the Untangle agent</span>
      </SectionTitle>
      <div className="card p-4 sm:p-5">
        {turns.length ? (
          <ol className="space-y-4" aria-label="Conversation" aria-live="polite">
            {turns.map((t, i) => (
              <li key={i} className={t.role === "user" ? "flex justify-end" : ""}>
                {t.role === "user" ? (
                  <p className="max-w-[85%] whitespace-pre-wrap rounded-lg bg-accent-soft px-3 py-2 text-[0.92rem] text-ink">{t.content}</p>
                ) : (
                  <div className="max-w-full">
                    {t.steps?.length ? (
                      <p className="mb-1.5 text-[0.76rem] text-ink-3">
                        {t.steps.map((s) => `${TOOL_LABEL[s.tool] ?? s.tool}${s.input ? `: ${s.input}` : ""}${s.ok ? "" : " (no result)"}`).join(" · ")}
                      </p>
                    ) : null}
                    <p className="whitespace-pre-wrap text-[0.92rem] leading-relaxed text-ink">{t.content}</p>
                  </div>
                )}
              </li>
            ))}
            {busy ? (
              <li className="flex items-center gap-2 text-[0.85rem] text-ink-3">
                <LoaderCircle size={15} className="animate-spin motion-reduce:animate-none" aria-hidden /> Looking through the history…
              </li>
            ) : null}
          </ol>
        ) : (
          <div>
            <p className="text-[0.9rem] text-ink-2">
              Ask why something in {repo ?? "the selected repository"} is the way it is. The agent looks up decisions, evidence and people
              in the indexed history and cites what it finds. No token or setup needed.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {STARTERS.map((q) => (
                <button key={q} type="button" className="btn btn-line btn-sm" disabled={busy || !repo} onClick={() => void send(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        <div ref={endRef} />
        <form
          className="mt-4 flex items-end gap-2 border-t border-rule pt-4"
          onSubmit={(e) => {
            e.preventDefault();
            void send(draft);
          }}
        >
          <label htmlFor={inputId} className="sr-only">Message the agent</label>
          <textarea
            id={inputId}
            className="field min-h-[2.75rem] flex-1 resize-y"
            rows={1}
            maxLength={4000}
            placeholder={repo ? "Why is the retry limit 3?" : "Select a repository first"}
            value={draft}
            disabled={!repo}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void send(draft);
              }
            }}
          />
          <button type="submit" className="btn btn-primary" disabled={busy || !draft.trim() || !repo} aria-label="Send">
            {busy ? <LoaderCircle size={16} className="animate-spin motion-reduce:animate-none" aria-hidden /> : <ArrowUp size={16} aria-hidden />}
          </button>
        </form>
        {error ? <p role="alert" className="mt-2 text-[0.85rem] text-bad">{error}</p> : null}
        {turns.length ? (
          <button type="button" className="mt-2 text-[0.8rem] text-ink-3 underline-offset-4 hover:underline" onClick={() => { setTurns([]); setError(null); }}>
            Start a new conversation
          </button>
        ) : null}
      </div>
    </section>
  );
}

const TOOLS: [string, string][] = [
  ["ask_why", "Cited answer to “why is this like this?”, or a refusal with the person to ask."],
  ["list_decisions", "Every recorded decision about a file, config key, dependency or module, with its history."],
  ["decision_timeline", "What was in force on a date, and what has been replaced since."],
  ["who_to_ask", "The people with the most relevant history for a part of the code."],
  ["search_repository", "Find files, keys, dependencies, symbols and people by name."],
  ["remember_decision", "Record a decision the agent settled, so the next agent or engineer finds the reason."],
  ["recall_agent_notes", "Recent notes that coding agents recorded in a repository."],
  ["list_repositories", "The repositories this workspace has indexed."],
];

function endpoint(): string {
  if (typeof window === "undefined") return `${API_BASE}/mcp`;
  return new URL(`${API_BASE}/mcp`, window.location.origin).href;
}

function NewToken({ token }: { token: AgentToken }) {
  const url = endpoint();
  const claude = `claude mcp add --transport http untangle ${url} --header "Authorization: Bearer ${token.token}"`;
  const json = JSON.stringify({ mcpServers: { untangle: { type: "http", url, headers: { Authorization: `Bearer ${token.token}` } } } }, null, 2);
  return (
    <div className="card space-y-4 border-accent/40 p-4 sm:p-5" role="status">
      <p className="text-[0.9rem] text-ink">
        <strong>Copy this token now.</strong> Untangle keeps only a fingerprint of it, so it cannot be shown again.
      </p>
      <div className="flex items-center gap-2">
        <code className="t-code min-w-0 flex-1 truncate rounded-md bg-surface-2 px-3 py-2" aria-label="New token">{token.token}</code>
        <CopyButton text={token.token ?? ""} label="Copy token" />
      </div>
      <div>
        <p className="mb-1.5 text-[0.85rem] font-semibold text-ink">Claude Code</p>
        <div className="flex items-start gap-2">
          <pre className="code-block min-w-0 flex-1 overflow-x-auto whitespace-pre-wrap break-all text-[0.78rem]">{claude}</pre>
          <CopyButton text={claude} label="Copy command" />
        </div>
      </div>
      <div>
        <p className="mb-1.5 text-[0.85rem] font-semibold text-ink">Cursor and other MCP clients (mcp.json)</p>
        <div className="flex items-start gap-2">
          <pre className="code-block min-w-0 flex-1 overflow-x-auto text-[0.78rem]">{json}</pre>
          <CopyButton text={json} label="Copy configuration" />
        </div>
      </div>
    </div>
  );
}

function Tokens() {
  const { user } = useAuth();
  if (user?.guest) {
    return (
      <section className="space-y-2" aria-labelledby="tokens-heading">
        <SectionTitle>
          <span id="tokens-heading">Agent tokens</span>
        </SectionTitle>
        <p className="text-[0.88rem] text-ink-2">
          <Link href="/signup?next=/agents" className="font-semibold text-accent underline-offset-4 hover:underline">Create an account</Link>{" "}
          to connect your own agent. The built-in agent above works without one.
        </p>
      </section>
    );
  }
  return <TokenManager />;
}

function TokenManager() {
  const res = useResource("agent-tokens", (signal) => api.agentTokens(signal));
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<AgentToken | null>(null);
  const nameId = useId();

  async function create(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      setCreated(await api.createAgentToken(name.trim() || "Coding agent"));
      setName("");
      res.reload();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(token: AgentToken) {
    if (!window.confirm(`Revoke "${token.name}"? Agents using it lose access immediately.`)) return;
    try {
      await api.revokeAgentToken(token.id);
      if (created?.id === token.id) setCreated(null);
      res.reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <section className="space-y-4" aria-labelledby="tokens-heading">
      <SectionTitle hint={res.data ? `${res.data.tokens.length} of ${res.data.max}` : undefined}>
        <span id="tokens-heading">Agent tokens</span>
      </SectionTitle>
      <form onSubmit={create} className="card flex flex-wrap items-end gap-3 p-4">
        <div className="min-w-[14rem] flex-1">
          <label htmlFor={nameId} className="mb-1.5 block text-[0.85rem] font-medium text-ink">Token name</label>
          <input id={nameId} className="field" maxLength={60} placeholder="Claude Code on my laptop" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          <KeyRound size={15} aria-hidden /> {busy ? "Creating…" : "Create token"}
        </button>
      </form>
      {error ? <p role="alert" className="text-[0.85rem] text-bad">{error}</p> : null}
      {created ? <NewToken token={created} /> : null}
      {res.loading ? (
        <SkeletonLines rows={2} />
      ) : res.error ? (
        <ErrorState title="Tokens could not be loaded" error={res.error} onRetry={res.reload} />
      ) : res.data && res.data.tokens.length ? (
        <ul className="card divide-y divide-rule" aria-label="Your agent tokens">
          {res.data.tokens.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="font-semibold text-ink">{t.name}</p>
                <p className="t-num text-[0.8rem] text-ink-3">
                  <code className="t-code">{t.prefix}…</code> · created {fmtDay(t.created_at_iso)} ·{" "}
                  {t.last_used_at_iso ? `last used ${fmtDay(t.last_used_at_iso)}` : "not used yet"}
                </p>
              </div>
              <button type="button" className="btn btn-line btn-sm" onClick={() => void revoke(t)} aria-label={`Revoke ${t.name}`}>
                <Trash2 size={14} aria-hidden /> Revoke
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[0.88rem] text-ink-3">No tokens yet. Create one for each agent or machine, so you can revoke them separately.</p>
      )}
    </section>
  );
}

function Notes() {
  const { repo } = useRepo();
  const res = useResource(repo ? `agent-notes:${repo}` : null, (signal) => api.agentNotes(repo!, signal));
  // Notes are written by agents while this page is open: refresh when the tab regains focus.
  const reload = res.reload;
  useEffect(() => {
    const again = () => { if (document.visibilityState === "visible") reload(); };
    document.addEventListener("visibilitychange", again);
    return () => document.removeEventListener("visibilitychange", again);
  }, [reload]);
  if (!repo) return <NoRepository what="see notes from coding agents" />;
  return (
    <section className="space-y-4" aria-labelledby="notes-heading">
      <SectionTitle hint={res.data ? `${res.data.notes.length}` : undefined}>
        <span id="notes-heading">Decisions recorded by agents in {repo}</span>
      </SectionTitle>
      {res.loading ? (
        <SkeletonLines rows={3} />
      ) : res.error ? (
        <ErrorState title="Agent notes could not be loaded" error={res.error} onRetry={res.reload} />
      ) : res.data && res.data.notes.length ? (
        <ul className="space-y-3" aria-label="Agent notes">
          {res.data.notes.map((n) => (
            <li key={n.id} className="card p-4">
              <p className="flex flex-wrap items-center gap-2 text-[0.8rem] text-ink-3">
                <span className="chip">Agent note</span>
                <span className={n.status === "active" ? "text-ok" : "mark-superseded"}>{n.status}</span>
                <span>· {n.about.join(", ") || n.subject} · {n.topic}</span>
                <span>· {fmtDay(n.recorded_at_iso)}{n.recorded_by ? ` · for ${n.recorded_by}` : ""}</span>
              </p>
              <p className="mt-1.5 text-[0.95rem] text-ink">{n.decision}</p>
              {n.rationale ? <p className="mt-1 text-[0.88rem] text-ink-2">Why: {n.rationale}</p> : null}
              {externalHref(n.source_url) ? (
                <a href={externalHref(n.source_url)} target="_blank" rel="noreferrer" className="mt-1 inline-block text-[0.82rem] text-accent underline-offset-4 hover:underline">
                  Source
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="No agent has recorded a decision here yet">
          Connect an agent with a token above, then ask it to record a decision with <code className="t-code">remember_decision</code>.
        </EmptyState>
      )}
    </section>
  );
}

export function AgentsPage() {
  return (
    <div className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="t-display text-[2.1rem] leading-[1.05] text-ink sm:text-[2.4rem]">Agents</h1>
          <p className="mt-2 max-w-2xl text-[0.95rem] text-ink-2">
            Ask the built-in agent here, or give your own coding agent the same decision graph. Agent answers cite the
            repository&apos;s history and never replace it.
          </p>
        </div>
        <RepoSelect compact />
      </header>
      <BuiltInAgent />
      <div className="space-y-8 border-t border-rule pt-8">
        <div>
          <h2 className="text-[1.25rem] font-semibold text-ink">Use your own agent</h2>
          <p className="mt-1 max-w-2xl text-[0.9rem] text-ink-2">
            Prefer your own model or coding agent? Connect Claude Code, Cursor or any MCP client with a token. Before changing a value
            or a dependency, it can ask why it is the way it is; after settling something, it records the decision for the next person.
            Agent notes are labelled, attributed to you, and never replace evidence from the code history.
          </p>
        </div>
        <section aria-labelledby="tools-heading" className="space-y-3">
          <SectionTitle>
            <span id="tools-heading" className="flex items-center gap-2"><Bot size={16} aria-hidden /> What a connected agent can do</span>
          </SectionTitle>
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
            {TOOLS.map(([name, what]) => (
              <div key={name} className="text-[0.88rem]">
                <dt className="t-code text-ink">{name}</dt>
                <dd className="text-ink-2">{what}</dd>
              </div>
            ))}
          </dl>
        </section>
        <Tokens />
        <Notes />
      </div>
    </div>
  );
}
