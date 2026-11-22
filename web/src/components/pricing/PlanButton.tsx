"use client";

import type { RequestPlan } from "@/lib/pricing";

/** Fired when a plan's button is pressed; the pilot form selects that plan. */
export const PLAN_EVENT = "untangle:plan";

/** Jumps to the pilot form with this plan chosen. Without JavaScript it still jumps to the form. */
export function PlanButton({ plan, label, primary = false, className = "" }: { plan: RequestPlan; label: string; primary?: boolean; className?: string }) {
  return (
    <a
      href="#pilot"
      className={`btn ${primary ? "btn-primary" : "btn-line"} ${className}`}
      onClick={() => window.dispatchEvent(new CustomEvent<RequestPlan>(PLAN_EVENT, { detail: plan }))}
    >
      {label}
    </a>
  );
}
