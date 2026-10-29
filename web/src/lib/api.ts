import type { AskRequest, AskResponse, Health, MeetingDetail, MeetingSummary, PulseResponse, RepoSummary, Timeline, WhyPath } from "./types";
import * as sample from "./sample";

export const API_BASE = (process.env.NEXT_PUBLIC_UNTANGLE_API ?? "/api").replace(/\/+$/, "");
export const SAMPLE_MODE = process.env.NEXT_PUBLIC_UNTANGLE_SAMPLE === "1";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return String(e);
}

async function request<T>(path: string, init?: RequestInit & { signal?: AbortSignal }): Promise<T> {
  const url = `${API_BASE}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...(init?.headers ?? {}) },
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, "Could not reach Untangle. Check your connection and try again.");
  }
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) {
    const detail =
      body && typeof body === "object" ? (body as { detail?: unknown; error?: unknown }).detail ?? (body as { error?: unknown }).error : typeof body === "string" ? body : null;
    const msg = typeof detail === "string" ? detail : `${res.status} ${res.statusText} from ${path}`;
    throw new ApiError(res.status, msg, body);
  }
  return body as T;
}

const q = (params: Record<string, string | null | undefined>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v != null && v !== "") s.set(k, v);
  const str = s.toString();
  return str ? `?${str}` : "";
};

export const api = {
  health: (signal?: AbortSignal): Promise<Health> => (SAMPLE_MODE ? sample.sampleHealth() : request("/health", { signal })),

  repos: (signal?: AbortSignal): Promise<RepoSummary[]> => (SAMPLE_MODE ? sample.sampleRepos() : request("/repos", { signal })),

  ask: (body: AskRequest, signal?: AbortSignal): Promise<AskResponse> =>
    SAMPLE_MODE ? sample.sampleAsk(body) : request("/ask", { method: "POST", body: JSON.stringify(body), signal }),

  decision: (id: string, signal?: AbortSignal): Promise<WhyPath> =>
    SAMPLE_MODE ? sample.sampleDecision(id) : request(`/decisions/${encodeURIComponent(id)}`, { signal }),

  timeline: (repo: string, atIso: string, signal?: AbortSignal): Promise<Timeline> =>
    SAMPLE_MODE ? sample.sampleTimeline(atIso) : request(`/timeline${q({ repo, at: atIso })}`, { signal }),

  pulse: (repo: string, signal?: AbortSignal): Promise<PulseResponse> =>
    SAMPLE_MODE ? sample.samplePulse(repo) : request(`/pulse${q({ repo })}`, { signal }),

  meetings: (repo: string, signal?: AbortSignal): Promise<MeetingSummary[]> =>
    SAMPLE_MODE ? sample.sampleMeetings(repo) : request(`/meetings${q({ repo })}`, { signal }),

  meeting: (id: string, signal?: AbortSignal): Promise<MeetingDetail> =>
    SAMPLE_MODE ? sample.sampleMeeting(id) : request(`/meetings/${encodeURIComponent(id)}`, { signal }),

  ingestMeeting: (body: FormData): Promise<{ meeting_id: string; utterances: number; decisions: number }> => {
    if (SAMPLE_MODE) return Promise.reject(new ApiError(400, "Uploads are available in the live app."));
    return request("/kt/ingest", { method: "POST", body });
  },
};

/** Resolves a citation or evidence link: absolute URLs open in a new tab, decision ids go to the why-path page. */
export function hrefFor(id: string, kind: string, url?: string | null): { href: string; external: boolean } | null {
  if (kind === "decision" || id.startsWith("dec:")) return { href: `/decisions/${encodeURIComponent(id)}`, external: false };
  if (kind === "meeting" || id.startsWith("mtg:") || id.startsWith("meeting:")) return { href: `/meetings/${encodeURIComponent(id)}`, external: false };
  if (kind === "utterance" || id.startsWith("utt:")) {
    const m = /^utt:(mtg:.+)#(\d+)$/.exec(id);
    if (m) return { href: `/meetings/${encodeURIComponent(m[1])}#utt-${Number(m[2])}`, external: false };
  }
  if (url) {
    if (/^https?:\/\//i.test(url)) return { href: url, external: true };
    return { href: url, external: false };
  }
  return null;
}
