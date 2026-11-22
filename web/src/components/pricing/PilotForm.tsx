"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { PILOT_DAYS, REQUEST_PLAN_LABELS, TRANSITION_ENGINEERS, type RequestPlan } from "@/lib/pricing";
import type { PilotReceipt } from "@/lib/types";
import { PLAN_EVENT } from "./PlanButton";

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

interface Draft {
  name: string;
  email: string;
  company: string;
  role: string;
  teamSize: string;
  plan: RequestPlan;
  message: string;
  website: string;
}

const EMPTY: Draft = { name: "", email: "", company: "", role: "", teamSize: "", plan: "transition", message: "", website: "" };

function problem(d: Draft): string | null {
  if (!d.name.trim()) return "Enter your name.";
  if (!EMAIL.test(d.email.trim())) return "Enter a work email address, such as you@company.com.";
  if (!d.company.trim()) return "Enter your company.";
  const size = Number(d.teamSize);
  if (!Number.isInteger(size) || size < 1) return "Enter how many engineers work on the codebase.";
  return null;
}

/** The sales conversation starts here: a pilot or plan request, answered within one working day. */
export function PilotForm() {
  const id = useId();
  const nameRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<(PilotReceipt & { email: string; name: string }) | null>(null);

  useEffect(() => {
    const choose = (event: Event) => {
      const plan = (event as CustomEvent<RequestPlan>).detail;
      if (plan in REQUEST_PLAN_LABELS) setDraft((d) => ({ ...d, plan }));
      setReceipt(null);
      // Wait for the jump to the form, then put the cursor in the first field.
      window.setTimeout(() => nameRef.current?.focus({ preventScroll: true }), 50);
    };
    window.addEventListener(PLAN_EVENT, choose);
    return () => window.removeEventListener(PLAN_EVENT, choose);
  }, []);

  const set = (key: keyof Draft) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setDraft((d) => ({ ...d, [key]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const reason = problem(draft);
    if (reason) {
      setError(reason);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const sent = await api.requestPilot({
        name: draft.name.trim(), email: draft.email.trim(), company: draft.company.trim(), role: draft.role.trim() || undefined,
        team_size: Number(draft.teamSize), plan: draft.plan, message: draft.message.trim() || undefined, website: draft.website || undefined,
      });
      setReceipt({ ...sent, email: draft.email.trim(), name: draft.name.trim() });
      setDraft(EMPTY);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (receipt) {
    return (
      <div role="status" className="card p-5 sm:p-6" data-testid="pilot-receipt">
        <h3 className="t-display text-[1.5rem] text-ink">Thank you, {receipt.name.split(" ")[0]}.</h3>
        <p className="mt-2 text-[0.95rem] leading-relaxed text-ink-2">
          Your reference is <strong className="t-code text-[0.95rem] text-ink">{receipt.reference}</strong>. We will reply to {receipt.email} {receipt.follow_up} to
          {receipt.plan === "transition" ? ` set up your ${PILOT_DAYS}-day pilot on one real handover.` : ` talk through the ${REQUEST_PLAN_LABELS[receipt.plan]} plan.`}
        </p>
        <p className="mt-3 text-[0.88rem] text-ink-3">
          While you wait, you can <Link href="/signup?next=/repositories" className="font-semibold text-accent underline-offset-4 hover:underline">start free</Link> on a public repository.
        </p>
        <button type="button" onClick={() => setReceipt(null)} className="btn btn-ghost btn-sm mt-4 -ml-2">Send another request</button>
      </div>
    );
  }

  const field = "field mt-1";
  return (
    <form onSubmit={submit} noValidate className="card relative space-y-4 p-5 sm:p-6" aria-label="Pilot request">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor={`${id}-name`} className="text-[0.88rem] font-semibold text-ink">Your name</label>
          <input ref={nameRef} id={`${id}-name`} value={draft.name} onChange={set("name")} autoComplete="name" maxLength={120} required className={field} />
        </div>
        <div>
          <label htmlFor={`${id}-email`} className="text-[0.88rem] font-semibold text-ink">Work email</label>
          <input id={`${id}-email`} type="email" value={draft.email} onChange={set("email")} autoComplete="email" maxLength={254} required className={field} />
        </div>
        <div>
          <label htmlFor={`${id}-company`} className="text-[0.88rem] font-semibold text-ink">Company</label>
          <input id={`${id}-company`} value={draft.company} onChange={set("company")} autoComplete="organization" maxLength={160} required className={field} />
        </div>
        <div>
          <label htmlFor={`${id}-role`} className="text-[0.88rem] font-semibold text-ink">Role <span className="font-normal text-ink-3">(optional)</span></label>
          <input id={`${id}-role`} value={draft.role} onChange={set("role")} autoComplete="organization-title" maxLength={120} placeholder="Delivery lead" className={field} />
        </div>
        <div>
          <label htmlFor={`${id}-plan`} className="text-[0.88rem] font-semibold text-ink">Plan</label>
          <select id={`${id}-plan`} value={draft.plan} onChange={set("plan")} className={field}>
            {(Object.keys(REQUEST_PLAN_LABELS) as RequestPlan[]).map((p) => (
              <option key={p} value={p}>{REQUEST_PLAN_LABELS[p]}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-size`} className="text-[0.88rem] font-semibold text-ink">Engineers on the codebase</label>
          <input id={`${id}-size`} type="number" inputMode="numeric" min={1} step={1} value={draft.teamSize} onChange={set("teamSize")} required className={`${field} t-num`}
            aria-describedby={draft.plan === "transition" ? `${id}-size-hint` : undefined} />
          {draft.plan === "transition" ? (
            <p id={`${id}-size-hint`} className="mt-1 text-[0.78rem] text-ink-3">One pack covers up to {TRANSITION_ENGINEERS} engineers.</p>
          ) : null}
        </div>
      </div>
      <div>
        <label htmlFor={`${id}-message`} className="text-[0.88rem] font-semibold text-ink">What is changing hands? <span className="font-normal text-ink-3">(optional)</span></label>
        <textarea id={`${id}-message`} value={draft.message} onChange={set("message")} maxLength={2000} rows={3} className={field}
          placeholder="The billing service moves to a new team in January; two of its engineers are serving notice." />
      </div>
      {/* People never see this field; automated submitters fill it in, and the server then stores nothing. */}
      <div aria-hidden="true" className="absolute -left-[10000px] h-px w-px overflow-hidden">
        <label htmlFor={`${id}-website`}>Website</label>
        <input id={`${id}-website`} tabIndex={-1} autoComplete="off" value={draft.website} onChange={set("website")} />
      </div>
      {error ? <p role="alert" className="text-[0.88rem] text-bad">{error}</p> : null}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <button type="submit" disabled={busy} className="btn btn-primary">{busy ? "Sending…" : draft.plan === "transition" ? `Request a ${PILOT_DAYS}-day pilot` : "Send request"}</button>
        <p className="text-[0.8rem] text-ink-3">We reply within one working day. No card needed.</p>
      </div>
    </form>
  );
}
