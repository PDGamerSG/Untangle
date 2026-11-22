/**
 * Plans and prices: the one place the website reads them from. The finale and pitch decks quote the same numbers,
 * so change them together. Prices are Indian rupees and exclude 18% GST.
 */

export type PlanId = "free" | "team" | "transition" | "enterprise";
/** Plans someone can ask about on the pilot form; Free needs no conversation. */
export type RequestPlan = Exclude<PlanId, "free">;

export interface PlanFeature {
  text: string;
  /** Not available yet: shown with its rollout note instead of as included. */
  rollout?: string;
}

export interface Plan {
  id: PlanId;
  name: string;
  /** Who it is for, in one line. */
  audience: string;
  price: string;
  unit: string;
  /** A short line under the price: minimums, billing, the pilot. */
  terms: string;
  features: PlanFeature[];
  cta: { label: string; href?: string; plan?: RequestPlan };
  recommended?: boolean;
}

export const GST_RATE = 0.18;
export const TEAM_SEAT_PRICE = 1499;
export const TEAM_MINIMUM_SEATS = 5;
export const TRANSITION_PRICE = 49999;
export const TRANSITION_DAYS = 90;
export const TRANSITION_ENGINEERS = 25;
export const PILOT_DAYS = 14;
export const FREE_QUESTIONS_PER_HOUR = 40;
/** The closest competitor's published list price, per user per month, used only as an anchor. */
export const COMPETITOR_PRICE_USD = 29;

const ROLLOUT = "rolling out, Q1 2027";

export const PLANS: readonly Plan[] = [
  {
    id: "free",
    name: "Free",
    audience: "For individual engineers and open-source maintainers.",
    price: "₹0",
    unit: "for ever",
    terms: "No card. Public repositories.",
    features: [
      { text: "Public GitHub repositories" },
      { text: "Ask why, with citations, or a clear refusal" },
      { text: "Timeline, feature map, Pulse, pre-flight checks and briefings" },
      { text: `${FREE_QUESTIONS_PER_HOUR} questions an hour per person` },
      { text: "Handover calls in Hindi, Hinglish and English" },
      { text: "Coding agents over MCP" },
    ],
    cta: { label: "Start free", href: "/signup?next=/repositories" },
  },
  {
    id: "team",
    name: "Team",
    audience: "For a team that owns a codebase and keeps losing the people who know why.",
    price: "₹1,499",
    unit: "per engineer a month",
    terms: `From ${TEAM_MINIMUM_SEATS} engineers. Billed monthly, cancel any time.`,
    features: [
      { text: "Everything in Free" },
      { text: "Higher question and handover limits for every engineer" },
      { text: "Priority imports and re-imports of your repositories" },
      { text: "Email support, answered within one working day" },
      { text: "Private repositories through a GitHub App", rollout: ROLLOUT },
      { text: "Team workspaces with roles", rollout: ROLLOUT },
    ],
    cta: { label: "Talk to us about Team", plan: "team" },
  },
  {
    id: "transition",
    name: "Transition Pack",
    audience: "For the lead taking over an application while its builders serve notice.",
    price: "₹49,999",
    unit: "per application handover",
    terms: `One payment. ${TRANSITION_DAYS} days, up to ${TRANSITION_ENGINEERS} engineers. The first ${PILOT_DAYS} days are a free pilot.`,
    features: [
      { text: "Everything in Team for the whole handover" },
      { text: "Guided import of the application with our team" },
      { text: "Every handover call transcribed and checked against the code" },
      { text: "Pulse list of knowledge at risk before the last working day" },
      { text: "A day-one briefing for every new joiner" },
      { text: "Reviews with us on day 30 and day 90, then continue on Team or stop" },
    ],
    cta: { label: `Start a ${PILOT_DAYS}-day pilot`, plan: "transition" },
    recommended: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    audience: "For 100 or more engineers, or code that cannot leave your network.",
    price: "Custom",
    unit: "annual agreement",
    terms: "Invoice billing and a service-level agreement.",
    features: [
      { text: "Everything in Team" },
      { text: "Self-hosted on your own servers: Untangle is MIT-licensed" },
      { text: "Several transitions a year at a fixed rate" },
      { text: "A named contact for your delivery leads" },
      { text: "Single sign-on and audit exports", rollout: ROLLOUT },
    ],
    cta: { label: "Talk to us", plan: "enterprise" },
  },
];

export const REQUEST_PLAN_LABELS: Record<RequestPlan, string> = {
  transition: `Transition Pack (${PILOT_DAYS}-day pilot)`,
  team: "Team",
  enterprise: "Enterprise",
};

export function inr(value: number): string {
  return `₹${Math.round(value).toLocaleString("en-IN")}`;
}

/** ₹1.95 lakh, ₹42 crore: how Indian buyers read large amounts. Below a lakh, the full figure. */
export function inrShort(value: number): string {
  if (value >= 1e7) return `₹${trim(value / 1e7)} crore`;
  if (value >= 1e5) return `₹${trim(value / 1e5)} lakh`;
  return inr(value);
}

function trim(n: number): string {
  return n >= 100 ? Math.round(n).toLocaleString("en-IN") : n.toFixed(2).replace(/\.?0+$/, "");
}

export interface RoiInput {
  engineers: number;
  /** Fully loaded monthly cost of one engineer, in rupees. */
  monthlyCost: number;
  /** Hours each engineer stops spending on reconstructing reasons, per week. */
  hoursSavedPerWeek: number;
}

export interface RoiResult {
  hourlyCost: number;
  hoursSavedPerMonth: number;
  /** Engineering time recovered across the team in one month, in rupees. */
  monthlyValue: number;
  teamSeats: number;
  teamCost: number;
  teamReturn: number;
  transitionValue: number;
  transitionReturn: number;
  /** Days of recovered time that pay for the Transition Pack. */
  transitionPaybackDays: number;
}

/** 160 working hours a month; 52 weeks over 12 months. Stated on the page next to the result. */
export const HOURS_PER_MONTH = 160;
export const WEEKS_PER_MONTH = 52 / 12;

export function roi({ engineers, monthlyCost, hoursSavedPerWeek }: RoiInput): RoiResult {
  const people = Math.max(1, Math.round(engineers));
  const hourlyCost = Math.max(0, monthlyCost) / HOURS_PER_MONTH;
  const hoursSavedPerMonth = Math.max(0, hoursSavedPerWeek) * WEEKS_PER_MONTH;
  const monthlyValue = people * hourlyCost * hoursSavedPerMonth;
  const teamSeats = Math.max(TEAM_MINIMUM_SEATS, people);
  const teamCost = teamSeats * TEAM_SEAT_PRICE;
  const transitionPeople = Math.min(people, TRANSITION_ENGINEERS);
  const transitionValue = transitionPeople * hourlyCost * hoursSavedPerMonth * (TRANSITION_DAYS / 30);
  const dailyValue = (transitionPeople * hourlyCost * hoursSavedPerMonth) / 30;
  return {
    hourlyCost,
    hoursSavedPerMonth,
    monthlyValue,
    teamSeats,
    teamCost,
    teamReturn: teamCost > 0 ? monthlyValue / teamCost : 0,
    transitionValue,
    transitionReturn: transitionValue / TRANSITION_PRICE,
    transitionPaybackDays: dailyValue > 0 ? Math.ceil(TRANSITION_PRICE / dailyValue) : Infinity,
  };
}

export const ROI_DEFAULTS: RoiInput = { engineers: 10, monthlyCost: 120_000, hoursSavedPerWeek: 2 };
