import { SectionTitle } from "@/components/states";
import type { AskResponse } from "@/lib/types";

export function ConfidenceMeter({ confidence }: { confidence: AskResponse["confidence"] }) {
  const pct = Math.round(Math.max(0, Math.min(1, confidence.score)) * 100);
  const tone = confidence.label === "high" ? "var(--ok)" : confidence.label === "medium" ? "var(--warn)" : "var(--bad)";
  return (
    <section aria-label="Confidence">
      <SectionTitle hint="computed from graph signals only, never from the model">Confidence</SectionTitle>
      <div className="card p-3.5">
        <div className="flex items-center gap-3">
          <div
            role="meter"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            aria-label={`Confidence ${pct}%, ${confidence.label}`}
            className="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-3"
          >
            <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${pct}%`, background: tone }} />
          </div>
          <span className="t-num w-12 text-right text-[1.05rem] font-semibold text-ink">{pct}%</span>
          <span className="rounded-md px-2 py-0.5 text-[0.74rem] font-bold uppercase tracking-wider" style={{ color: tone, background: "color-mix(in srgb, " + tone + " 14%, transparent)" }}>
            {confidence.label}
          </span>
        </div>
        {confidence.reasons.length ? (
          <ul className="mt-3 grid gap-1 text-[0.85rem] text-ink-2 sm:grid-cols-2">
            {confidence.reasons.map((r, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-[0.45em] inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-ink-3" aria-hidden />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  );
}
