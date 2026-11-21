import { BENCHMARK, type BenchmarkCell } from "@/lib/benchmarks";
import { fmtDay } from "@/lib/format";

const INTENT: Record<string, string> = {
  config_value: "Config value", supersession: "What replaced it", entity_why: "Why a file", dependency: "Dependency",
  refuse: "Should refuse", who_to_ask: "Who to ask", kt: "Handover call",
};

function verdict(cell: BenchmarkCell | undefined, intent: string): { text: string; good: boolean | null } {
  if (!cell) return { text: "—", good: null };
  if (intent === "refuse") return cell.outcome === "refused" ? { text: "Refused", good: true } : { text: "Answered anyway", good: false };
  if (cell.outcome !== "answered") return { text: cell.outcome, good: false };
  const checks = [cell.evidence, cell.supersession, cell.person].filter((x) => x !== "-");
  if (!checks.length) return { text: "Answered", good: null };
  const ok = checks.every((x) => x === "yes");
  return { text: ok ? "Correct evidence" : "Missed evidence", good: ok };
}

function Verdict({ cell, intent }: { cell: BenchmarkCell | undefined; intent: string }) {
  const v = verdict(cell, intent);
  return <span className={v.good === true ? "text-ok" : v.good === false ? "text-bad" : "text-ink-2"}>{v.text}</span>;
}

/** The recorded evaluation of Untangle's graph answers against vector-only search over the same text. */
export function BenchmarksPage() {
  const b = BENCHMARK;
  return (
    <div className="space-y-9">
      <header className="max-w-3xl">
        <h1 className="t-display text-[2.2rem] leading-[1.04] text-ink sm:text-[2.6rem]">How often Untangle is right</h1>
        <p className="mt-2 text-[0.98rem] leading-relaxed text-ink-2">
          Every answer is scored against a gold set written for one public repository: the cited evidence, whether a replaced value is
          reported, the person to ask, and whether questions the history cannot answer are refused. The same questions go to a vector-only
          search over the same text, with no decisions and no refusal logic.
        </p>
      </header>

      <section aria-labelledby="scope-heading" className="card-muted p-4 text-[0.88rem] leading-relaxed text-ink-2">
        <h2 id="scope-heading" className="font-semibold text-ink">What this measures, and what it does not</h2>
        <p className="mt-1">
          Recorded {fmtDay(b.recorded)} on <span className="t-code">knadh/listmonk</span> from <span className="t-code">{b.gold}</span>: {b.questions} questions,
          {" "}{b.verified} with expectations checked against the repository&apos;s history and {b.unverified} written without that check, which are scored but
          reported apart. The handover rationale comes from a clearly labelled synthetic transcript. A set this small shows behaviour, not general accuracy.
        </p>
      </section>

      <section aria-labelledby="summary-heading">
        <div className="sec-head"><h2 id="summary-heading">Verified questions</h2><span className="sec-hint">graph answer vs vector-only search</span></div>
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[30rem] text-left text-[0.9rem]">
            <thead className="text-[0.8rem] text-ink-3">
              <tr className="border-b border-rule">
                <th scope="col" className="px-4 py-2 font-semibold">Measure</th>
                <th scope="col" className="px-4 py-2 font-semibold">Untangle graph</th>
                <th scope="col" className="px-4 py-2 font-semibold">Vector-only</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {b.metrics.map((m) => (
                <tr key={m.name}>
                  <th scope="row" className="px-4 py-2 font-medium text-ink">{m.name}</th>
                  <td className="t-num px-4 py-2 font-semibold text-ink">{m.graph}</td>
                  <td className="t-num px-4 py-2 text-ink-2">{m.baseline}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[0.82rem] text-ink-3">
          Refusal precision is the share of refusals that were right to refuse; recall is the share of unanswerable questions that were refused.
        </p>
      </section>

      <section aria-labelledby="questions-heading">
        <div className="sec-head"><h2 id="questions-heading">Every question</h2><span className="sec-hint">{b.rows.length} questions</span></div>
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[36rem] text-left text-[0.86rem]">
            <thead className="text-[0.78rem] text-ink-3">
              <tr className="border-b border-rule">
                <th scope="col" className="px-4 py-2 font-semibold">Question</th>
                <th scope="col" className="px-3 py-2 font-semibold">Kind</th>
                <th scope="col" className="px-3 py-2 font-semibold">Untangle graph</th>
                <th scope="col" className="px-4 py-2 font-semibold">Vector-only</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {b.rows.map((r) => (
                <tr key={r.id}>
                  <th scope="row" className="t-code px-4 py-2 font-medium text-ink">
                    {r.id}{r.verified ? null : <span className="ml-1.5 font-sans text-[0.74rem] font-normal text-ink-3">unverified</span>}
                  </th>
                  <td className="px-3 py-2 text-ink-2">{INTENT[r.intent] ?? r.intent}</td>
                  <td className="px-3 py-2"><Verdict cell={r.graph} intent={r.intent} /></td>
                  <td className="px-4 py-2"><Verdict cell={r.baseline} intent={r.intent} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="repro-heading">
        <div className="sec-head"><h2 id="repro-heading">Run it yourself</h2></div>
        <p className="text-[0.9rem] text-ink-2">After ingesting the repository and the sample transcript into your own Neo4j database:</p>
        <pre className="code-block mt-2 overflow-x-auto"><code>uv run untangle eval --repo knadh/listmonk --gold eval/gold/listmonk.yaml</code></pre>
        <p className="mt-2 text-[0.84rem] text-ink-3">The harness writes a Markdown and JSON report; this page is regenerated from it with <span className="t-code">scripts/build_benchmarks_page.py</span>.</p>
      </section>
    </div>
  );
}
