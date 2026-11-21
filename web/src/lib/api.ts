import type {
  Account,
  AgentNote,
  AgentToken,
  AskRequest,
  AskResponse,
  EntityResponse,
  GitHubIdentity,
  GitHubRepositories,
  GraphStats,
  Health,
  ImportJob,
  MeetingDetail,
  MeetingSummary,
  PulseResponse,
  RepoSummary,
  RepositoryChanges,
  RepositoryImports,
  RepositoryOverview,
  SavedRepository,
  SearchResponse,
  Timeline,
  WhyPath,
} from "./types";
import * as sample from "./sample";
import type { MapLoadProgress, RepositoryMap } from "./repository-map";

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

async function request<T>(path: string, init?: RequestInit & { signal?: AbortSignal }, timeoutMs = 45_000): Promise<T> {
  const url = `${API_BASE}${path}`;
  const deadline = AbortSignal.timeout(timeoutMs);
  const signal = init?.signal ? AbortSignal.any([init.signal, deadline]) : deadline;
  let res: Response;
  let text: string;
  try {
    res = await fetch(url, {
      ...init,
      signal,
      headers: { Accept: "application/json", ...(init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...(init?.headers ?? {}) },
    });
    text = await res.text();
  } catch (e) {
    if (deadline.aborted) throw new ApiError(408, "This is taking longer than expected. Please retry shortly.");
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, "Could not reach Untangle. Check your connection and try again.");
  }
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/auth/")) redirectToSignIn();
    throw new ApiError(res.status, describeFailure(res.status, body), body);
  }
  return body as T;
}

/** A sentence a person can act on, never a raw status line, validation dump or upstream error page. */
export function describeFailure(status: number, body: unknown): string {
  const detail = body && typeof body === "object" ? (body as { detail?: unknown; error?: unknown }).detail ?? (body as { error?: unknown }).error : null;
  if (typeof detail === "string" && detail.length <= 400) return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { loc?: unknown[]; msg?: string; type?: string; ctx?: { max_length?: number; min_length?: number } };
    const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1] ?? "input") : "input";
    if (first.type === "string_too_long" && first.ctx?.max_length) return `The ${field} is too long. Keep it under ${first.ctx.max_length} characters.`;
    if (first.type === "string_too_short") return `The ${field} is too short.`;
    if (first.type === "missing") return `The ${field} is required.`;
    return `The ${field} is not valid${first.msg ? `: ${first.msg.toLowerCase()}` : ""}.`;
  }
  if (status === 401) return "Sign in to continue.";
  if (status === 403) return "You do not have permission to do that.";
  if (status === 404) return "That item was not found.";
  if (status === 413) return "That upload is too large.";
  if (status === 429) return "Too many requests. Please wait a moment and try again.";
  if (status === 504 || status === 408) return "This is taking longer than expected. Please retry shortly.";
  if (status >= 500) return "Untangle could not finish this request. Please retry shortly.";
  return "The request could not be completed.";
}

let redirecting = false;
/** The session expired or was revoked: return to sign-in, then back to this page. */
function redirectToSignIn() {
  if (typeof window === "undefined" || redirecting || SAMPLE_MODE) return;
  const here = window.location.pathname + window.location.search;
  if (here.startsWith("/login") || here.startsWith("/signup")) return;
  redirecting = true;
  // Called outside React (from the fetch client), so the router is not available here.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${encodeURIComponent(here)}`);
}

const q = (params: Record<string, string | null | undefined>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v != null && v !== "") s.set(k, v);
  const str = s.toString();
  return str ? `?${str}` : "";
};

async function loadRepositoryMap(repo: string, offset: number, signal?: AbortSignal, onProgress?: (progress: MapLoadProgress) => void): Promise<RepositoryMap> {
  const page = (structurePage: number) => request<RepositoryMap>(`/repository-map${q({ repo, offset: String(offset), limit: "40", structure_page: String(structurePage) })}`, { signal });
  const data = await page(0);
  let current = data;
  const report = () => onProgress?.({ loaded: data.files.length + data.imports.length + data.features.length,
    total: data.total_files + (data.total_imports ?? data.imports.length) + (data.total_features ?? data.features.length) });
  report();
  const maxPages = Math.max(1, data.total_files + (data.total_imports ?? 0) + (data.total_features ?? 0));
  for (let next = 1; current.structure_has_more; next++) {
    if (next > maxPages) throw new ApiError(502, "Map loading made no progress. Please retry.");
    current = await page(next);
    if (current.structure_page !== next || current.head_sha !== data.head_sha || current.indexed_at_iso !== data.indexed_at_iso ||
        current.total_files !== data.total_files || current.total_imports !== data.total_imports || current.total_features !== data.total_features) {
      throw new ApiError(409, "The repository changed while its map was loading. Please retry to load the complete version.");
    }
    if (current.structure_has_more && !current.files.length && !current.imports.length && !current.features.length)
      throw new ApiError(502, "Map loading made no progress. Please retry.");
    data.files.push(...current.files);
    data.imports.push(...current.imports);
    data.features.push(...current.features);
    report();
  }
  const known = new Set(data.files.map(file => file.path));
  if (known.size !== data.total_files || known.size !== data.files.length ||
      (data.total_imports != null && data.imports.length !== data.total_imports) ||
      (data.total_features != null && data.features.length !== data.total_features) ||
      data.imports.some(edge => !known.has(edge.source) || !known.has(edge.target))) {
    throw new ApiError(502, "The repository map is incomplete. Please retry or refresh its import from Repositories.");
  }
  if (data.index_status === "basic") {
    const groups = new Map<string, string[]>();
    for (const file of data.files.filter(f => f.alive)) {
      const directory = file.path.includes("/") ? file.path.slice(0, file.path.lastIndexOf("/")) : ".";
      const members = groups.get(directory) ?? [];
      members.push(file.path); groups.set(directory, members);
    }
    data.features = [...groups].sort(([a], [b]) => a.localeCompare(b)).map(([name, entrypoints]) => ({
      id: `feature:${repo}:${name}`, name, entrypoints, source: "directory", description: "Inferred directory group; not a verified product feature.",
    }));
    data.total_features = data.features.length;
  }
  data.structure_has_more = false;
  return data;
}

export const api = {
  me: (): Promise<{ user: Account }> => request("/auth/me"),
  login: (body: { email: string; password: string }): Promise<{ user: Account }> =>
    request("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  register: (body: { email: string; password: string; name?: string }): Promise<{ user: Account }> =>
    request("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  logout: (): Promise<void> => request("/auth/logout", { method: "POST" }),
  startGuest: (): Promise<{ user: Account }> => request("/auth/guest", { method: "POST" }),
  deleteAccount: (): Promise<void> => request("/auth/account", { method: "DELETE" }),
  agentTokens: (signal?: AbortSignal): Promise<{ tokens: AgentToken[]; max: number }> => request("/auth/tokens", { signal }),
  createAgentToken: (name: string): Promise<AgentToken> => request("/auth/tokens", { method: "POST", body: JSON.stringify({ name }) }),
  revokeAgentToken: (id: string): Promise<void> => request(`/auth/tokens/${encodeURIComponent(id)}`, { method: "DELETE" }),
  agentChat: (body: { repo: string | null; messages: { role: "user" | "assistant"; content: string }[] }, signal?: AbortSignal):
    Promise<{ reply: string; steps: { tool: string; input: string; ok: boolean }[] }> =>
    SAMPLE_MODE
      ? Promise.reject(new ApiError(400, "The agent is available in the live app."))
      : request("/agent/chat", { method: "POST", body: JSON.stringify(body), signal }, 120_000),
  agentNotes: (repo: string, signal?: AbortSignal): Promise<{ repo: string; notes: AgentNote[] }> =>
    request(`/agent-notes${q({ repo })}`, { signal }),
  deleteMeeting: (id: string): Promise<void> => {
    if (SAMPLE_MODE) return Promise.reject(new ApiError(400, "Deleting is available in the live app."));
    return request(`/meetings/${encodeURIComponent(id)}`, { method: "DELETE" });
  },

  health: (signal?: AbortSignal): Promise<Health> => (SAMPLE_MODE ? sample.sampleHealth() : request("/health", { signal })),

  repos: (signal?: AbortSignal): Promise<RepoSummary[]> => (SAMPLE_MODE ? sample.sampleRepos() : request("/repos", { signal })),

  ask: (body: AskRequest, signal?: AbortSignal): Promise<AskResponse> =>
    SAMPLE_MODE ? sample.sampleAsk(body) : request("/ask", { method: "POST", body: JSON.stringify(body), signal }, body.mode === "graph" ? 60_000 : 90_000),

  decision: (id: string, signal?: AbortSignal): Promise<WhyPath> =>
    SAMPLE_MODE ? sample.sampleDecision(id) : request(`/decisions/${encodeURIComponent(id)}`, { signal }),

  entity: (id: string, signal?: AbortSignal): Promise<EntityResponse> =>
    SAMPLE_MODE ? Promise.reject(new ApiError(404, "Entity pages are available in the live app.")) : request(`/entities/${encodeURIComponent(id)}`, { signal }),

  search: (repo: string, query: string, signal?: AbortSignal): Promise<SearchResponse> =>
    SAMPLE_MODE ? Promise.resolve({ entities: [], people: [] }) : request(`/search${q({ repo, q: query })}`, { signal }),

  stats: (repo: string, signal?: AbortSignal): Promise<GraphStats> =>
    SAMPLE_MODE
      ? Promise.resolve({ nodes: 0, relationships: 0, labels: {}, relationship_types: {} })
      : request(`/stats${q({ repo })}`, { signal }),

  repositoryMap: (repo: string, offset: number, signal?: AbortSignal, onProgress?: (progress: MapLoadProgress) => void): Promise<RepositoryMap> =>
    SAMPLE_MODE ? Promise.reject(new ApiError(400, "Repository maps require a live indexed repository.")) : loadRepositoryMap(repo, offset, signal, onProgress),

  timeline: (repo: string, atIso: string, signal?: AbortSignal): Promise<Timeline> =>
    SAMPLE_MODE ? sample.sampleTimeline(atIso) : request(`/timeline${q({ repo, at: atIso })}`, { signal }),

  pulse: (repo: string, signal?: AbortSignal): Promise<PulseResponse> =>
    SAMPLE_MODE ? sample.samplePulse(repo) : request(`/pulse${q({ repo })}`, { signal }),

  meetings: (repo: string, signal?: AbortSignal): Promise<MeetingSummary[]> =>
    SAMPLE_MODE ? sample.sampleMeetings(repo) : request(`/meetings${q({ repo })}`, { signal }),

  meeting: (id: string, signal?: AbortSignal): Promise<MeetingDetail> =>
    SAMPLE_MODE ? sample.sampleMeeting(id) : request(`/meetings/${encodeURIComponent(id)}`, { signal }),

  repositoryImports: (signal?: AbortSignal): Promise<RepositoryImports> =>
    SAMPLE_MODE ? Promise.reject(new ApiError(400, "Adding repositories is available in the live app.")) : request("/repository-imports", { signal }),

  repositoryImport: (id: string, signal?: AbortSignal): Promise<ImportJob> =>
    SAMPLE_MODE ? Promise.reject(new ApiError(404, "Adding repositories is available in the live app.")) : request(`/repository-imports/${encodeURIComponent(id)}`, { signal }),

  /** Queues a public GitHub repository, or returns the active or recent job for it. Posting a failed one retries it. */
  importRepository: (repository: string): Promise<ImportJob> =>
    SAMPLE_MODE
      ? Promise.reject(new ApiError(400, "Adding repositories is available in the live app."))
      : request("/repository-imports", { method: "POST", body: JSON.stringify({ repository }) }),

  authProviders: (signal?: AbortSignal): Promise<{ github: boolean }> =>
    SAMPLE_MODE ? Promise.resolve({ github: false }) : request("/auth/providers", { signal }),
  githubIdentity: (signal?: AbortSignal): Promise<{ github: GitHubIdentity | null }> =>
    SAMPLE_MODE ? Promise.resolve({ github: null }) : request("/auth/github", { signal }),
  disconnectGitHub: (): Promise<void> => request("/auth/github", { method: "DELETE" }),
  githubRepositories: (owner: string | null, signal?: AbortSignal): Promise<GitHubRepositories> =>
    SAMPLE_MODE
      ? Promise.resolve({ owner: null, connected: false, repositories: [] })
      : request(`/github/repositories${owner ? q({ owner }) : ""}`, { signal }),
  savedRepositories: (signal?: AbortSignal): Promise<{ repositories: SavedRepository[]; max: number }> =>
    SAMPLE_MODE ? Promise.resolve({ repositories: [], max: 0 }) : request("/my/repositories", { signal }),
  saveRepository: (repository: string): Promise<{ repo: string; saved: boolean }> =>
    request("/my/repositories", { method: "POST", body: JSON.stringify({ repository }) }),
  removeSavedRepository: (repo: string): Promise<void> => request(`/my/repositories${q({ repo })}`, { method: "DELETE" }),
  repositoryChanges: (repo: string, signal?: AbortSignal): Promise<RepositoryChanges> =>
    request(`/my/repositories/changes${q({ repo })}`, { signal }),

  repositoryOverview: (repo: string, signal?: AbortSignal): Promise<RepositoryOverview> =>
    SAMPLE_MODE ? Promise.reject(new ApiError(404, "The repository inventory is available in the live app.")) : request(`/repository-overview${q({ repo })}`, { signal }),

  ingestMeeting: (body: FormData): Promise<{ meeting_id: string; utterances: number; decisions: number }> => {
    if (SAMPLE_MODE) return Promise.reject(new ApiError(400, "Uploads are available in the live app."));
    return request("/kt/ingest", { method: "POST", body }, 300_000);
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
  return safeLink(url);
}

/** Only web links and same-site paths are followed; `javascript:`, `data:` and `//host` links are dropped. */
export function safeLink(url?: string | null): { href: string; external: boolean } | null {
  if (!url) return null;
  if (url.startsWith("/") && !url.startsWith("//") && !url.startsWith("/\\")) return { href: url, external: false };
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "https:" || parsed.protocol === "http:") return { href: parsed.href, external: true };
  } catch {
    return null;
  }
  return null;
}

/** The href for an external evidence link, or undefined when it is not a plain web address. */
export function externalHref(url?: string | null): string | undefined {
  const link = safeLink(url);
  return link?.external ? link.href : undefined;
}
