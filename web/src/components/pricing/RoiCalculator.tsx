"use client";

import { useId, useState } from "react";
import { HOURS_PER_MONTH, PILOT_DAYS, ROI_DEFAULTS, TEAM_MINIMUM_SEATS, TRANSITION_DAYS, TRANSITION_ENGINEERS, inr, inrShort, roi, type RoiInput } from "@/lib/pricing";

const FIELDS: readonly { key: keyof RoiInput; label: string; hint: string; min: number; max: number; step: number }[] = [
  { key: "engineers", label: "Engineers on the codebase", hint: "Including new joiners", min: 1, max: 5000, step: 1 },
  { key: "monthlyCost", label: "Monthly cost of one engineer (₹)", hint: "Salary, benefits and overheads", min: 0, max: 2_000_000, step: 5000 },
  { key: "hoursSavedPerWeek", label: "Hours saved per engineer a week", hint: "Not hunting for why code is the way it is", min: 0, max: 20, step: 0.5 },
];

function times(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return `${n >= 10 ? Math.round(n) : n.toFixed(1)}×`;
}

/** What the plans return in recovered engineering time, from three numbers the buyer can change. */
export function RoiCalculator() {
  const id = useId();
  const [input, setInput] = useState<Record<keyof RoiInput, string>>({
    engineers: String(ROI_DEFAULTS.engineers),
    monthlyCost: String(ROI_DEFAULTS.monthlyCost),
    hoursSavedPerWeek: String(ROI_DEFAULTS.hoursSavedPerWeek),
  });
  const values: RoiInput = {
    engineers: Number(input.engineers) || 0,
    monthlyCost: Number(input.monthlyCost) || 0,
    hoursSavedPerWeek: Number(input.hoursSavedPerWeek) || 0,
  };
  const r = roi(values);
  const capped = values.engineers > TRANSITION_ENGINEERS;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:gap-10">
      <form className="space-y-4" onSubmit={(e) => e.preventDefault()} aria-label="Return calculator inputs">
        {FIELDS.map((f) => (
          <div key={f.key}>
            <label htmlFor={`${id}-${f.key}`} className="block text-[0.88rem] font-semibold text-ink">{f.label}</label>
            <input
              id={`${id}-${f.key}`}
              type="number"
              inputMode="decimal"
              min={f.min}
              max={f.max}
              step={f.step}
              value={input[f.key]}
              onChange={(e) => setInput((prev) => ({ ...prev, [f.key]: e.target.value }))}
              className="field t-num mt-1"
              aria-describedby={`${id}-${f.key}-hint`}
            />
            <p id={`${id}-${f.key}-hint`} className="mt-1 text-[0.78rem] text-ink-3">{f.hint}</p>
          </div>
        ))}
      </form>

      <div>
        <dl className="stat-strip grid-cols-1 sm:grid-cols-2" aria-live="polite">
          <div>
            <dt>Engineering time recovered a month</dt>
            <dd className="t-num" data-testid="roi-monthly-value">{inr(r.monthlyValue)}</dd>
            <dd className="stat-note">{Math.round(r.hoursSavedPerMonth * Math.max(1, Math.round(values.engineers)))} hours at {inr(r.hourlyCost)} an hour</dd>
          </div>
          <div>
            <dt>Team plan a month</dt>
            <dd className="t-num" data-testid="roi-team-cost">{inr(r.teamCost)}</dd>
            <dd className="stat-note">
              {r.teamSeats} engineers{values.engineers < TEAM_MINIMUM_SEATS ? ` (the ${TEAM_MINIMUM_SEATS}-engineer minimum)` : ""}, before GST
            </dd>
          </div>
          <div>
            <dt>Return on Team</dt>
            <dd className="t-num" data-testid="roi-team-return">{times(r.teamReturn)}</dd>
            <dd className="stat-note">Time recovered for each rupee spent</dd>
          </div>
          <div>
            <dt>Transition Pack over {TRANSITION_DAYS} days</dt>
            <dd className="t-num" data-testid="roi-transition-return">{times(r.transitionReturn)}</dd>
            <dd className="stat-note">
              {inrShort(r.transitionValue)} recovered
              {Number.isFinite(r.transitionPaybackDays) ? `; pays for itself in ${r.transitionPaybackDays} days` : ""}
              {capped ? ` (for ${TRANSITION_ENGINEERS} engineers, the pack's limit)` : ""}
            </dd>
          </div>
        </dl>
        <p className="mt-3 text-[0.8rem] leading-relaxed text-ink-3">
          Uses {HOURS_PER_MONTH} working hours a month. Developers spend about 58% of their time understanding code (
          <a href="https://xin-xia.github.io/publication/TSE17.pdf" className="underline underline-offset-2 hover:text-ink">Xia et al., 2018</a>
          ); the hours saved is an assumption, so put in your own. The first {PILOT_DAYS} days of a Transition Pack are free, which is how you measure it.
        </p>
      </div>
    </div>
  );
}
