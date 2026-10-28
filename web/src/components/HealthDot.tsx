"use client";

import { api, API_BASE, SAMPLE_MODE } from "@/lib/api";
import { useResource } from "@/lib/hooks";

export function HealthDot() {
  const health = useResource("health", (signal) => api.health(signal));
  const state = health.loading ? "loading" : health.error ? "down" : health.data?.ok ? "ok" : "warn";
  const colour =
    state === "ok" ? "bg-ok" : state === "down" ? "bg-bad" : state === "warn" ? "bg-warn" : "bg-ink-3";
  const d = health.data;
  const lines = health.loading
    ? ["Checking the API…"]
    : health.error
      ? [`API unreachable: ${health.error}`]
      : d
        ? [
            `Neo4j ${d.neo4j.version}${d.neo4j.aura ? " (AuraDB)" : ""}`,
            `LLM: ${d.llm.backend}${d.llm.model ? ` / ${d.llm.model}` : ""}`,
            `Embeddings: ${d.embed.backend} (${d.embed.dim} dims)`,
            SAMPLE_MODE ? "Sample mode (fixtures)" : API_BASE,
          ]
        : ["No health data"];
  return (
    <div className="group relative ml-1 flex items-center">
      <button
        type="button"
        className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-surface-2"
        aria-label={`API status: ${state}. ${lines.join(". ")}`}
        aria-describedby="health-tip"
        onClick={() => health.reload()}
      >
        <span className={`relative inline-block h-2.5 w-2.5 rounded-full ${colour}`}>
          {state === "ok" ? <span className="absolute inset-0 animate-ping rounded-full bg-ok opacity-40" /> : null}
        </span>
      </button>
      <div
        id="health-tip"
        role="tooltip"
        className="pointer-events-none absolute right-0 top-full z-50 mt-1 w-max max-w-[18rem] rounded-lg border border-rule bg-surface px-3 py-2 text-left text-[0.78rem] leading-relaxed text-ink-2 opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
      >
        {lines.map((l) => (
          <div key={l} className="t-num">
            {l}
          </div>
        ))}
      </div>
    </div>
  );
}
