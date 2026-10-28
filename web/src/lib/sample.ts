/**
 * Sample mode: serves the fixtures in web/sample/*.json instead of the API.
 * Enabled only by NEXT_PUBLIC_KYUN_SAMPLE=1; the API client never falls back to this on failure.
 * The fixtures are snapshots of real API responses from the live graph (scripts/export_sample.py), never
 * hand-written: sample mode shows exactly what Kyun answered, including the real vector-only baseline.
 */
import health from "../../sample/health.json";
import repos from "../../sample/repos.json";
import decisions from "../../sample/decisions.json";
import meetings from "../../sample/meetings.json";
import meetingDetail from "../../sample/meeting.json";
import pulse from "../../sample/pulse.json";
import askConcurrency from "../../sample/ask/concurrency.json";
import askConcurrencyAsOf from "../../sample/ask/concurrency-asof.json";
import askStillUse from "../../sample/ask/still-use.json";
import askWho from "../../sample/ask/who.json";
import askChanged from "../../sample/ask/changed.json";
import askRefusal from "../../sample/ask/refusal.json";
import type {
  AskRequest,
  AskResponse,
  DecisionCard,
  Health,
  MeetingDetail,
  MeetingSummary,
  PulseResponse,
  Ref,
  RepoSummary,
  Timeline,
  WhyPath,
} from "./types";

type PathRow = {
  evidence: Ref[];
  older: string[];
  newer: string[];
  motivated_by: Ref[];
  implemented_by: Ref[];
  cypher: { name: string; params: Record<string, unknown>; rows: number }[];
};

const cards = decisions.cards as Record<string, DecisionCard>;
const paths = decisions.paths as Record<string, PathRow>;

function delay(ms: number) {
  return new Promise<void>((r) => setTimeout(r, ms));
}

export class SampleNotFound extends Error {
  status = 404;
}

export async function sampleHealth(): Promise<Health> {
  await delay(120);
  return health as Health;
}

export async function sampleRepos(): Promise<RepoSummary[]> {
  await delay(150);
  return repos as RepoSummary[];
}

/** app.concurrency changed in commit 894ede5 on this date; an "as of" date before it gets the earlier snapshot. */
const CONCURRENCY_CHANGED = Date.parse("2020-04-02T00:00:00Z");

/**
 * Picks the recorded answer whose question this one resembles. Recorded answers keep their own question text,
 * so a visitor always sees which question was actually asked; anything unrecognised gets the recorded refusal.
 */
export async function sampleAsk(req: AskRequest): Promise<AskResponse> {
  await delay(650);
  const q = req.question.toLowerCase();
  let res: AskResponse;
  if (/concurrency/.test(q)) {
    const at = req.at ? Date.parse(req.at) : NaN;
    res = (!Number.isNaN(at) && at < CONCURRENCY_CHANGED ? askConcurrencyAsOf : askConcurrency) as AskResponse;
  } else if (/still|lib\/pq|\bpq\b/.test(q)) res = askStillUse as AskResponse;
  else if (/who|ask about|owner|owns/.test(q)) res = askWho as AskResponse;
  else if (/changed|history|docker-compose/.test(q)) res = askChanged as AskResponse;
  else res = askRefusal as AskResponse;
  // the recorded baseline is the real vector-only answer; only show it when the comparison was asked for
  return { ...res, repo: req.repo, mode: req.mode, baseline: req.mode === "both" ? res.baseline : null };
}

export async function sampleDecision(id: string): Promise<WhyPath> {
  await delay(200);
  const card = cards[id];
  const path = paths[id];
  if (!card || !path) throw new SampleNotFound(`No decision ${id} in the sample data.`);
  return {
    decision: card,
    evidence: path.evidence,
    older: path.older.map((x) => cards[x]).filter(Boolean),
    newer: path.newer.map((x) => cards[x]).filter(Boolean),
    motivated_by: path.motivated_by,
    implemented_by: path.implemented_by,
    cypher: path.cypher,
  };
}

export async function sampleTimeline(atIso: string): Promise<Timeline> {
  await delay(180);
  const at = Date.parse(atIso);
  const all = Object.values(cards).filter((c) => c.status !== "retracted");
  const active = all
    .filter((c) => Date.parse(c.valid_from_iso) <= at && (c.valid_to_iso === null || at < Date.parse(c.valid_to_iso)))
    .sort((a, b) => Date.parse(b.valid_from_iso) - Date.parse(a.valid_from_iso));
  const superseded_since = all
    .filter((c) => c.valid_to_iso !== null && Date.parse(c.valid_to_iso) > at)
    .sort((a, b) => Date.parse(b.valid_to_iso!) - Date.parse(a.valid_to_iso!));
  return { at_iso: new Date(at).toISOString(), active, superseded_since };
}

export async function samplePulse(repo: string): Promise<PulseResponse> {
  await delay(220);
  return { ...(pulse as PulseResponse), repo };
}

export async function sampleMeetings(repo: string): Promise<MeetingSummary[]> {
  await delay(150);
  return (meetings as MeetingSummary[]).filter((m) => m.repo === repo);
}

export async function sampleMeeting(id: string): Promise<MeetingDetail> {
  await delay(220);
  const detail = meetingDetail as unknown as MeetingDetail;
  if (!detail || detail.id !== id) throw new SampleNotFound(`No meeting ${id} in the sample data.`);
  return detail;
}
