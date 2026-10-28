import Link from "next/link";
import { History } from "lucide-react";
import { fmtDay, signalLabel } from "@/lib/format";
import type { Supersession } from "@/lib/types";
import { InlineCode } from "./AnswerText";

export function SupersessionBanner({ items }: { items: Supersession[] }) {
  if (!items.length) return null;
  return (
    <section aria-label="Supersession" className="space-y-2">
      {items.map((s) => (
        <div key={`${s.newer}>${s.older}`} className="card flex gap-3 border-l-4 border-l-accent p-3.5">
          <History size={18} className="mt-0.5 shrink-0 text-accent" aria-hidden />
          <div className="min-w-0 text-[0.9rem] leading-relaxed">
            <p className="text-ink">
              <strong>This replaced</strong>{" "}
              <Link href={`/decisions/${encodeURIComponent(s.older)}`} className="mark-superseded underline-offset-4 hover:underline" title="Open the superseded decision">
                <InlineCode text={s.older_text ?? ""} />
              </Link>{" "}
              on <span className="t-num font-semibold">{fmtDay(s.at_iso)}</span>
              <span className="text-ink-3"> · signal: {signalLabel(s.signal)}</span>
            </p>
            <p className="mt-1 text-ink-2">
              Now:{" "}
              <Link href={`/decisions/${encodeURIComponent(s.newer)}`} className="font-medium text-ink underline-offset-4 hover:underline">
                <InlineCode text={s.newer_text ?? ""} />
              </Link>
            </p>
          </div>
        </div>
      ))}
    </section>
  );
}
