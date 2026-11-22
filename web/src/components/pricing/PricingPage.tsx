import Link from "next/link";
import { Check, Clock } from "lucide-react";
import { COMPETITOR_PRICE_USD, PILOT_DAYS, PLANS, TRANSITION_DAYS, TRANSITION_ENGINEERS, TRANSITION_PRICE, inr, type Plan } from "@/lib/pricing";
import { PilotForm } from "./PilotForm";
import { PlanButton } from "./PlanButton";
import { RoiCalculator } from "./RoiCalculator";

function PlanColumn({ plan }: { plan: Plan }) {
  const primary = Boolean(plan.recommended);
  return (
    <li className="flex flex-col p-5 sm:p-6" data-recommended={primary ? "true" : undefined} data-testid={`plan-${plan.id}`}>
      <h3 className="text-[1.05rem] font-semibold text-ink">{plan.name}</h3>
      <p className="mt-1 min-h-[2.6rem] text-[0.86rem] leading-snug text-ink-2">{plan.audience}</p>
      <p className="mt-4 flex flex-wrap items-baseline gap-x-2">
        <span className="t-display t-num text-[2.3rem] leading-none text-ink">{plan.price}</span>
        <span className="text-[0.86rem] text-ink-2">{plan.unit}</span>
      </p>
      <p className="mt-2 min-h-[2.4rem] text-[0.8rem] leading-snug text-ink-3">{plan.terms}</p>
      <div className="mt-4">
        {plan.cta.plan ? (
          <PlanButton plan={plan.cta.plan} label={plan.cta.label} primary={primary} className="w-full" />
        ) : (
          <Link href={plan.cta.href ?? "/signup"} className={`btn ${primary ? "btn-primary" : "btn-line"} w-full`}>{plan.cta.label}</Link>
        )}
      </div>
      <ul className="mt-5 space-y-2.5 border-t border-rule pt-4 text-[0.88rem] leading-snug">
        {plan.features.map((f) =>
          f.rollout ? (
            <li key={f.text} className="flex gap-2 text-ink-3">
              <Clock size={15} className="mt-0.5 shrink-0" aria-hidden />
              <span>
                {f.text} ({f.rollout})
              </span>
            </li>
          ) : (
            <li key={f.text} className="flex gap-2 text-ink-2">
              <Check size={15} className="mt-0.5 shrink-0 text-accent" aria-hidden />
              <span>{f.text}</span>
            </li>
          ),
        )}
      </ul>
    </li>
  );
}

const STEPS: readonly { when: string; title: string; text: string }[] = [
  {
    when: "Day 0",
    title: "Kick-off call",
    text: "We import the application's history with you, list who is leaving and which areas they own, and record the first handover call.",
  },
  {
    when: `Days 1–${PILOT_DAYS}`,
    title: "Free pilot",
    text: "New joiners ask why the code is like this and get cited answers or a clear refusal. Pulse lists the decisions with no recorded reason or a single owner: the questions to put to the leavers while they are still here.",
  },
  {
    when: "Day 30",
    title: "First review",
    text: "Together we read what the team asked, what Untangle refused and which gaps closed. You decide whether to continue; stopping costs nothing.",
  },
  {
    when: `Day ${TRANSITION_DAYS}`,
    title: "Handover closed",
    text: "Every area has a briefing and its evidence, exported as Markdown you keep. Continue on Team, or leave with your exports.",
  },
];

const WHY: readonly { today: string; untangle: string }[] = [
  { today: "Recorded KT calls nobody searches", untangle: "Calls in Hindi, Hinglish or English are transcribed and linked to the files and keys they mention, and flagged where they contradict the code." },
  { today: "KT documents that go stale the week they are written", untangle: "Decisions are versioned in time: what replaced what, and when, from the repository's own history." },
  { today: "Assistants that explain what code does, and guess why", untangle: "Every answer cites its evidence. With no evidence, Untangle says so and names the person most likely to know." },
];

const FAQ: readonly { q: string; a: React.ReactNode }[] = [
  { q: "Is GST included?", a: "No. Prices are in Indian rupees and exclude 18% GST, which appears on your invoice." },
  {
    q: "How do we pay?",
    a: "After the pilot we send a GST invoice and you pay by bank transfer. Team is billed monthly for the engineers who signed in that month, with the five-engineer minimum. There is no card checkout yet.",
  },
  {
    q: `What happens after the ${PILOT_DAYS}-day pilot?`,
    a: `You decide. Continue and we invoice the Transition Pack at ${inr(TRANSITION_PRICE)} for the full ${TRANSITION_DAYS} days; stop and you pay nothing. Your accounts stay on Free either way.`,
  },
  {
    q: "Does it work on private repositories?",
    a: "The hosted service reads public GitHub repositories today. Private repositories through a GitHub App are rolling out with pilot customers in the first quarter of 2027. Enterprise customers can run Untangle on their own servers.",
  },
  {
    q: "What happens to our handover calls?",
    a: "They are transcribed, linked to the code they mention and kept with your account. The person who uploaded a call can delete it at any time.",
  },
  {
    q: "What if Untangle does not know the answer?",
    a: "It refuses instead of guessing, shows the closest related records and names the person most likely to know. You are never charged per question.",
  },
  {
    q: "Can we run it ourselves?",
    a: "Yes. Untangle is open source under the MIT license, so you can run it from GitHub for free. Enterprise adds support, a service-level agreement and transitions at a fixed rate.",
  },
];

/** The public pricing page: plans, the return they buy, how a paid handover runs, and the way to start one. */
export function PricingPage() {
  return (
    <div className="space-y-16 sm:space-y-20">
      <header className="max-w-3xl">
        <h1 className="t-display text-[2.4rem] leading-[1.03] text-ink sm:text-[3.2rem]">Keep the why when people leave.</h1>
        <p className="mt-4 max-w-2xl text-[1.02rem] leading-relaxed text-ink-2 sm:text-[1.1rem]">
          Untangle answers why the code is like this, with the evidence, before the people who knew have gone. Start free on public repositories.
          When an application changes hands, one Transition Pack covers the whole handover, and the first {PILOT_DAYS} days are free.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <PlanButton plan="transition" label={`Start a ${PILOT_DAYS}-day pilot`} primary />
          <Link href="/signup?next=/repositories" className="btn btn-line">Start free</Link>
        </div>
      </header>

      <section aria-labelledby="plans-heading">
        <h2 id="plans-heading" className="sr-only">Plans</h2>
        <ul className="plan-sheet sm:grid-cols-2 xl:grid-cols-4">
          {PLANS.map((plan) => <PlanColumn key={plan.id} plan={plan} />)}
        </ul>
        <p className="mt-3 text-[0.8rem] leading-relaxed text-ink-3">
          Prices in Indian rupees, excluding 18% GST. Team costs about 40% less than comparable code-answer tools, which list at ${COMPETITOR_PRICE_USD} per user a month.
          A Transition Pack for {TRANSITION_ENGINEERS} engineers works out to {inr(TRANSITION_PRICE / (TRANSITION_ENGINEERS * (TRANSITION_DAYS / 30)))} per engineer a month.
        </p>
      </section>

      <section aria-labelledby="roi-heading">
        <div className="mb-5 max-w-2xl">
          <h2 id="roi-heading" className="t-display text-[1.75rem] text-ink sm:text-[2rem]">Work out the return</h2>
          <p className="mt-2 text-[0.95rem] leading-relaxed text-ink-2">
            The cost of a handover is the time a new team spends rebuilding reasons that already existed. Change the numbers to your own.
          </p>
        </div>
        <RoiCalculator />
      </section>

      <section aria-labelledby="why-heading">
        <div className="mb-4 max-w-2xl">
          <h2 id="why-heading" className="t-display text-[1.75rem] text-ink sm:text-[2rem]">What teams use today, and what changes</h2>
        </div>
        <dl className="divide-y divide-rule border-y border-rule">
          {WHY.map((row) => (
            <div key={row.today} className="grid gap-1 py-4 sm:grid-cols-[minmax(0,18rem)_minmax(0,1fr)] sm:gap-8">
              <dt className="text-[0.95rem] font-semibold text-ink">{row.today}</dt>
              <dd className="text-[0.92rem] leading-relaxed text-ink-2">{row.untangle}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="steps-heading">
        <div className="mb-4 max-w-2xl">
          <h2 id="steps-heading" className="t-display text-[1.75rem] text-ink sm:text-[2rem]">How a Transition Pack runs</h2>
          <p className="mt-2 text-[0.95rem] leading-relaxed text-ink-2">
            {inr(TRANSITION_PRICE)} for one application, {TRANSITION_DAYS} days and up to {TRANSITION_ENGINEERS} engineers. It is paid from the transition budget, so no seats need buying.
          </p>
        </div>
        <ol className="divide-y divide-rule border-y border-rule">
          {STEPS.map((s) => (
            <li key={s.when} className="grid gap-1 py-4 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
              <p className="t-num text-[0.88rem] font-semibold text-accent">{s.when}</p>
              <div>
                <h3 className="text-[0.98rem] font-semibold text-ink">{s.title}</h3>
                <p className="mt-1 text-[0.92rem] leading-relaxed text-ink-2">{s.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="faq-heading" className="grid gap-6 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)] lg:gap-10">
        <h2 id="faq-heading" className="t-display text-[1.75rem] text-ink sm:text-[2rem]">Questions buyers ask</h2>
        <dl className="divide-y divide-rule border-y border-rule">
          {FAQ.map((item) => (
            <div key={item.q} className="py-4">
              <dt className="text-[0.95rem] font-semibold text-ink">{item.q}</dt>
              <dd className="mt-1 text-[0.92rem] leading-relaxed text-ink-2">{item.a}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section id="pilot" aria-labelledby="pilot-heading" className="scroll-mt-24 grid gap-6 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)] lg:gap-10">
        <div>
          <h2 id="pilot-heading" className="t-display text-[1.75rem] text-ink sm:text-[2rem]">Start a pilot</h2>
          <p className="mt-2 text-[0.92rem] leading-relaxed text-ink-2">
            Tell us about the application that is changing hands. We set up a {PILOT_DAYS}-day pilot on one real handover, or answer your questions about Team and Enterprise.
          </p>
        </div>
        <PilotForm />
      </section>
    </div>
  );
}
