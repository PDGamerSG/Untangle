import { AlertTriangle } from "lucide-react";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

export function SkeletonLines({ rows = 3, className = "" }: { rows?: number; className?: string }) {
  const widths = ["w-11/12", "w-4/5", "w-2/3", "w-3/4", "w-1/2"];
  return (
    <div role="status" aria-label="Loading" className={`space-y-2.5 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className={`skeleton h-3.5 ${widths[i % widths.length]}`} />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = "Something went wrong" }: { error: string; onRetry?: () => void; title?: string }) {
  return (
    <div role="alert" aria-live="assertive" className="card border-bad/40 bg-bad-soft p-4">
      <p className="flex items-center gap-2 font-semibold text-ink">
        <AlertTriangle size={16} className="text-bad" /> {title}
      </p>
      <p className="mt-1 break-words text-[0.9rem] text-ink-2">{error}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="btn btn-line btn-sm mt-3">
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="card-muted p-6 text-center">
      <p className="font-semibold text-ink-2">{title}</p>
      {children ? <div className="mt-1 text-[0.9rem] text-ink-3">{children}</div> : null}
    </div>
  );
}

export function SectionTitle({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div className="sec-head">
      <h3>{children}</h3>
      {hint ? <span className="sec-hint">{hint}</span> : null}
    </div>
  );
}
