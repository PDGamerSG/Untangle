import type { CitationKind } from "./types";

const DAY = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const DAY_TIME = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "UTC",
});

/** "14 Mar 2023" from an ISO string; returns the input when it does not parse. */
export function fmtDay(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : DAY.format(d);
}

/** "14 Mar 2023, 10:22 UTC" */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : `${DAY_TIME.format(d)} UTC`;
}

/** "00:36" or "1:02:05" from milliseconds. */
export function fmtOffset(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** "27 min" or "1 h 12 min" */
export function fmtDuration(ms: number): string {
  const min = Math.round(ms / 60000);
  if (min < 1) return `${Math.round(ms / 1000)} s`;
  if (min < 60) return `${min} min`;
  return `${Math.floor(min / 60)} h ${min % 60} min`;
}

/** Today's date as YYYY-MM-DD in UTC (for date inputs). */
export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Infers the citation kind from an id prefix when the citations map does not carry it. */
export function kindFromId(id: string): CitationKind {
  const p = id.split(":")[0]?.toLowerCase();
  switch (p) {
    case "dec":
    case "decision":
      return "decision";
    case "pr":
    case "pull":
      return "pr";
    case "issue":
    case "incident":
      return "issue";
    case "commit":
    case "sha":
      return "commit";
    case "comment":
    case "review":
      return "comment";
    case "doc":
    case "document":
    case "adr":
      return "document";
    case "utt":
    case "utterance":
      return "utterance";
    case "person":
      return "person";
    case "meeting":
      return "meeting";
    default:
      return "entity";
  }
}

/** Normalises the kinds the API may send ("pull_request", "pr", "PullRequest") to the UI's set. */
export function normaliseKind(kind: string | undefined | null, id: string): CitationKind {
  const k = (kind ?? "").toLowerCase();
  if (k === "pullrequest" || k === "pull_request" || k === "pr") return "pr";
  if (k === "adr" || k === "doc" || k === "document") return "document";
  if (k === "incident" || k === "issue") return "issue";
  if (["decision", "commit", "comment", "utterance", "person", "meeting"].includes(k)) return k as CitationKind;
  return kindFromId(id);
}

export const KIND_LABEL: Record<CitationKind, string> = {
  decision: "Decision",
  pr: "PR",
  issue: "Issue",
  commit: "Commit",
  comment: "Comment",
  document: "Document",
  utterance: "Utterance",
  person: "Person",
  meeting: "Meeting",
  entity: "Entity",
};

/** Graph label -> citation kind, for colouring subgraph nodes with the same palette as chips. */
export function kindFromLabel(label: string): CitationKind | "config" | "file" | "module" | "dependency" | "symbol" | "repo" {
  switch (label) {
    case "Decision":
      return "decision";
    case "PullRequest":
      return "pr";
    case "Issue":
    case "Incident":
      return "issue";
    case "Commit":
      return "commit";
    case "Comment":
      return "comment";
    case "Document":
      return "document";
    case "Utterance":
      return "utterance";
    case "Person":
      return "person";
    case "Meeting":
      return "meeting";
    case "ConfigKey":
      return "config";
    case "File":
      return "file";
    case "Module":
      return "module";
    case "Dependency":
      return "dependency";
    case "Symbol":
      return "symbol";
    case "Repo":
      return "repo";
    default:
      return "entity";
  }
}

/** Short, human label for a decision predicate. */
export function predicateLabel(p: string): string {
  const map: Record<string, string> = {
    config_value: "config value",
    uses_dependency: "uses dependency",
    dependency_version: "dependency version",
    adr_status: "ADR status",
    reverted: "reverted",
    changed: "changed",
    chose: "chose",
    constraint: "constraint",
    workaround_for: "workaround for",
    owner: "owner",
    deprecated: "deprecated",
    kt_said: "said in handover",
  };
  return map[p] ?? p.replaceAll("_", " ");
}

export function signalLabel(s: string): string {
  const map: Record<string, string> = {
    config_diff: "config diff",
    lockfile_diff: "lockfile diff",
    adr_status: "ADR status",
    revert_commit: "revert commit",
    pr_merge: "PR merge",
    supersedes_text: "'supersedes' in text",
    llm_pr_thread: "LLM over PR thread",
    llm_kt: "LLM over handover call",
  };
  return map[s] ?? s.replaceAll("_", " ");
}

export function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

/** Splits "owner/name" into a short display form. */
export function shortRepo(fullName: string): string {
  return fullName.split("/").pop() ?? fullName;
}
