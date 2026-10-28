"use client";

import { ChevronDown } from "lucide-react";
import { CopyButton } from "@/components/CopyButton";
import { Subgraph } from "./Subgraph";
import type { CypherCall, Why } from "@/lib/types";

export function CypherList({ calls }: { calls: CypherCall[] }) {
  if (!calls.length) return <p className="text-[0.85rem] text-ink-3">No Cypher recorded.</p>;
  return (
    <ol className="divide-y divide-rule overflow-hidden rounded-lg border border-rule">
      {calls.map((c, i) => {
        const params = JSON.stringify(c.params ?? {}, null, 0);
        const copyText = c.text ? `// ${c.name}\n// params: ${params}\n${c.text}` : `cypher/${c.name}.cypher  params: ${params}`;
        return (
          <li key={`${c.name}-${i}`} className="flex items-start gap-3 bg-surface px-3 py-2">
            <span className="t-num mt-0.5 w-5 shrink-0 text-right text-[0.75rem] text-ink-3">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-baseline gap-x-2">
                <code className="t-code font-semibold text-ink">{c.name}</code>
                <span className="t-num text-[0.76rem] text-ink-3">
                  {c.rows} {c.rows === 1 ? "row" : "rows"}
                </span>
              </p>
              <code className="t-code mt-0.5 block break-all text-ink-2">{params}</code>
              {c.text ? <pre className="code-block mt-1.5 max-h-48 overflow-auto">{c.text}</pre> : null}
            </div>
            <CopyButton text={copyText} label="Copy" />
          </li>
        );
      })}
    </ol>
  );
}

export function WhyPanel({ why, defaultOpen = false }: { why: Why; defaultOpen?: boolean }) {
  const llm = why.llm;
  return (
    <details className="group card" open={defaultOpen}>
      <summary className="flex items-center justify-between gap-3 px-4 py-3">
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-semibold text-ink">Why this answer</span>
          <span className="text-[0.8rem] text-ink-3">
            route <code className="t-code text-ink-2">{why.route}</code> · {why.cypher.length} Cypher {why.cypher.length === 1 ? "call" : "calls"} ·{" "}
            {why.subgraph.nodes.length} nodes
          </span>
        </span>
        <ChevronDown size={16} className="shrink-0 text-ink-3 transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="space-y-5 border-t border-rule px-4 py-4">
        <dl className="grid gap-x-6 gap-y-2 text-[0.85rem] sm:grid-cols-[auto_1fr]">
          <dt className="text-ink-3">Route</dt>
          <dd>
            <code className="t-code text-ink">{why.route}</code>
          </dd>
          <dt className="text-ink-3">Language model</dt>
          <dd className="text-ink-2">
            {llm.used ? (
              <>
                Composed by <code className="t-code text-ink">{llm.backend}</code>
                {llm.model ? (
                  <>
                    {" "}
                    / <code className="t-code text-ink">{llm.model}</code>
                  </>
                ) : null}
                , citations validated against the evidence.
              </>
            ) : (
              <>
                Template answer rendered from the graph; no model call{llm.backend ? ` (backend: ${llm.backend}${llm.model ? ` / ${llm.model}` : ""})` : ""}.
              </>
            )}
          </dd>
        </dl>
        <div>
          <h4 className="mb-2 text-[0.78rem] font-bold uppercase tracking-wider text-ink-3">Cypher calls, in order</h4>
          <CypherList calls={why.cypher} />
        </div>
        <div>
          <h4 className="mb-2 text-[0.78rem] font-bold uppercase tracking-wider text-ink-3">Subgraph read for this answer</h4>
          <Subgraph subgraph={why.subgraph} />
        </div>
      </div>
    </details>
  );
}
