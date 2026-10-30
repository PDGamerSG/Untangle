"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowUpRight, ExternalLink, GitCommitHorizontal, UserRound } from "lucide-react";
import { KindTag } from "./Chip";
import { DecisionCard } from "./DecisionCard";
import { EmptyState, ErrorState, SectionTitle, Skeleton, SkeletonLines } from "./states";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { fmtDay, kindFromLabel } from "@/lib/format";
import type { EntityResponse } from "@/lib/types";

const HIDDEN_FIELDS = new Set(["id", "label", "name", "tokens", "repo", "embedding"]);

const FIELD_NAMES: Record<string, string> = {
  path: "Path",
  key: "Key",
  ecosystem: "Ecosystem",
  current_version: "Current version",
  current_value: "Current value",
  kind: "Kind",
  file: "Declared in",
};

/** Scalar facts about the entity, plus a nested `{path}` such as the file a dependency is declared in. */
function facts(entity: EntityResponse["entity"]): [string, string][] {
  const out: [string, string][] = [];
  for (const [k, v] of Object.entries(entity)) {
    if (HIDDEN_FIELDS.has(k) || v === null || v === undefined || v === "") continue;
    if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") out.push([FIELD_NAMES[k] ?? k.replace(/_/g, " "), String(v)]);
    else if (typeof v === "object" && v && "path" in v && typeof (v as { path: unknown }).path === "string") out.push([FIELD_NAMES[k] ?? k, (v as { path: string }).path]);
  }
  return out;
}

export function EntityPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ? decodeURIComponent(params.id) : null;
  const res = useResource(id ? `entity:${id}` : null, (signal) => api.entity(id!, signal));

  if (res.loading)
    return (
      <div className="space-y-4" role="status" aria-label="Loading entity">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-9 w-2/3" />
        <SkeletonLines rows={5} />
      </div>
    );
  if (res.error) return <ErrorState title={res.errorStatus === 404 ? "This entity is not in the graph" : "Could not load this entity"} error={res.error} onRetry={res.reload} />;
  const data = res.data;
  if (!data) return null;

  const e = data.entity;
  const name = e.name ?? e.key ?? e.path ?? e.id;
  const active = data.decisions.filter((d) => d.status === "active");
  const older = data.decisions.filter((d) => d.status !== "active");
  const details = facts(e);

  return (
    <div className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 max-w-3xl">
          <KindTag kind={kindFromLabel(e.label)}>{e.label}</KindTag>
          <h1 className="t-display mt-2 break-words text-[2.2rem] leading-[1.04] text-ink sm:text-[2.8rem]">{name}</h1>
          {details.length ? (
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[0.88rem]">
              {details.map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-ink-3">{k}</dt>
                  <dd className="t-code min-w-0 break-all text-ink-2">{v}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </div>
        <Link href={`/ask?question=${encodeURIComponent(`why is ${name} like this?`)}`} className="btn btn-primary btn-sm">
          Ask why <ArrowUpRight size={13} aria-hidden />
        </Link>
      </header>

      <section aria-labelledby="entity-decisions">
        <SectionTitle hint={`${active.length} in force, ${older.length} superseded`}>
          <span id="entity-decisions">Decisions about it</span>
        </SectionTitle>
        {data.decisions.length ? (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {[...active, ...older].map((d) => (
              <DecisionCard key={d.id} decision={d} />
            ))}
          </div>
        ) : (
          <EmptyState title="No decision is recorded about this yet">Untangle has the entity but no commit, review or call that explains it.</EmptyState>
        )}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_2fr]">
        <section aria-labelledby="entity-people">
          <SectionTitle>
            <span id="entity-people">People to ask</span>
          </SectionTitle>
          {data.people.length ? (
            <ul className="card divide-y divide-rule">
              {data.people.map((p) => (
                <li key={p.id} className="px-4 py-3">
                  <p className="flex items-center gap-2 text-[0.92rem] font-semibold text-ink">
                    <UserRound size={14} className="text-ink-3" aria-hidden />
                    {p.login ? (
                      <a href={`https://github.com/${p.login}`} target="_blank" rel="noreferrer" className="underline-offset-4 hover:underline">
                        {p.name ?? p.login}
                      </a>
                    ) : (
                      p.name
                    )}
                  </p>
                  {p.why ? <p className="mt-0.5 text-[0.82rem] leading-relaxed text-ink-2">{p.why}</p> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[0.88rem] text-ink-3">No owner found in the history.</p>
          )}
        </section>

        <section aria-labelledby="entity-commits">
          <SectionTitle>
            <span id="entity-commits">Recent commits</span>
          </SectionTitle>
          {data.recent_commits.length ? (
            <ul className="card divide-y divide-rule">
              {data.recent_commits.map((c) => (
                <li key={c.id} className="flex items-start gap-3 px-4 py-3">
                  <GitCommitHorizontal size={15} className="mt-1 shrink-0 text-ink-3" aria-hidden />
                  <div className="min-w-0 text-[0.9rem]">
                    <p className="text-ink">
                      {c.url ? (
                        <a href={c.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline-offset-4 hover:underline">
                          {c.title ?? c.sha?.slice(0, 7)} <ExternalLink size={12} aria-hidden />
                        </a>
                      ) : (
                        c.title
                      )}
                    </p>
                    <p className="t-num mt-0.5 text-[0.78rem] text-ink-3">
                      <span className="t-code">{c.sha?.slice(0, 7)}</span>
                      {c.author?.name ? ` · ${c.author.name}` : ""}
                      {c.authored_at_iso ? ` · ${fmtDay(c.authored_at_iso)}` : ""}
                      {c.pr ? ` · ${c.pr.title}` : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[0.88rem] text-ink-3">No commits touch it.</p>
          )}
        </section>
      </div>
    </div>
  );
}
