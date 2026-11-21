"use client";

import { useEffect, useState } from "react";

/** Estimates are ranges, never fabricated stage progress or a guaranteed countdown. */
export function WaitStatus({ label, min = 5, max = 15, onCancel, cancelLabel = "Cancel" }: {
  label: string; min?: number; max?: number; onCancel?: () => void; cancelLabel?: string;
}) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);
  return <div className="card-muted flex flex-wrap items-center justify-between gap-3 p-4" role="status">
    <div className="space-y-1 text-[0.85rem]">
      <p className="font-semibold text-ink">{label}</p>
      <p className="text-ink-2">{elapsed > max ? "Taking longer than estimated. You can keep waiting or retry." : `Estimated wait: ${min}–${max} seconds. First requests may take longer.`}</p>
      <p className="t-num text-ink-3" aria-live="off">{elapsed}s elapsed</p>
    </div>
    {onCancel ? <button type="button" className="btn btn-line btn-sm" onClick={onCancel}>{cancelLabel}</button> : null}
  </div>;
}
