/**
 * Types mirroring docs/CONTRACTS.md §6. Keep field names identical to the API;
 * the UI never renames or reshapes what the backend sends.
 */

export type CitationKind =
  | "decision"
  | "pr"
  | "issue"
  | "commit"
  | "comment"
  | "document"
  | "utterance"
  | "person"
  | "meeting"
  | "entity";

export type DecisionStatus = "active" | "superseded" | "retracted";

export type DecisionKind = "config_value" | "dependency" | "adr" | "revert" | "change" | "rationale" | "kt";

export interface Health {
  ok: boolean;
  status?: "ok" | "degraded";
  neo4j: { version: string; aura: boolean };
  graph?: { ok: boolean; version?: string | null; aura?: boolean; edition?: string | null };
  llm: { backend: string; model: string };
  embed: { backend: string; dim: number };
  optional_backends?: {
    llm: { backend: string; available: boolean };
    embeddings: { backend: string; available: boolean };
    sarvam: { configured: boolean };
  };
  sarvam?: { configured: boolean; model?: string | null };
}

export interface CommitCard {
  id: string;
  sha?: string | null;
  title?: string | null;
  url?: string | null;
  authored_at_iso?: string | null;
  author?: PersonCard | null;
  pr?: Ref | null;
  paths: string[];
}

export interface EntityResponse {
  entity: { id: string; label: string; name?: string | null; path?: string | null; key?: string | null; [field: string]: unknown };
  decisions: DecisionCard[];
  people: PersonCard[];
  recent_commits: CommitCard[];
}

export interface EntityHit extends EntityRef {
  key?: string | null;
  score: number;
}

export interface PersonHit {
  id: string;
  name?: string | null;
  login?: string | null;
  score: number;
}

export interface SearchResponse {
  entities: EntityHit[];
  people: PersonHit[];
}

export interface GraphStats {
  nodes: number;
  relationships: number;
  labels: Record<string, number>;
  relationship_types: Record<string, number>;
}

export interface RepoSummary {
  full_name: string;
  head_sha: string;
  commit_count: number;
  ingested_at_iso: string;
  counts: { commits: number; prs: number; issues: number; decisions: number; meetings: number };
}

export interface EntityRef {
  id: string;
  label: string;
  name: string;
  path?: string | null;
}

export interface Ref {
  id: string;
  kind: CitationKind | string;
  title: string;
  url?: string | null;
  excerpt?: string | null;
  at_iso?: string | null;
  author?: string | null;
}

export interface PersonCard {
  id: string;
  name: string;
  login?: string | null;
  why?: string | null;
}

export interface DecisionCard {
  id: string;
  kind: DecisionKind | string;
  key: string;
  subject: string;
  predicate: string;
  object: string;
  text: string;
  rationale: string | null;
  status: DecisionStatus;
  valid_from_iso: string;
  valid_to_iso: string | null;
  confidence: number;
  signal: string;
  about: EntityRef[];
  decided_in: Ref | null;
  stated_by: PersonCard | null;
}

export type PulseCategory = "contradiction" | "drift" | "ownership_gap" | "rationale_gap" | "stale";

export interface PulseSummary {
  active_decisions: number;
  risks: number;
  critical: number;
  coverage: number;
  contradictions: number;
  drift: number;
  ownership_gaps: number;
}

export interface PulseRisk {
  id: string;
  category: PulseCategory;
  score: number;
  reasons: string[];
  entity: EntityRef;
  decision: DecisionCard;
  owner: PersonCard | null;
  evidence: Ref[];
  contradictions: Ref[];
  last_touched_iso: string | null;
  owner_last_active_iso: string | null;
}

export interface PulseResponse {
  repo: string;
  generated_at_iso: string;
  summary: PulseSummary;
  risks: PulseRisk[];
}

export interface WhyPath {
  decision: DecisionCard;
  evidence: Ref[];
  older: DecisionCard[];
  newer: DecisionCard[];
  motivated_by: Ref[];
  implemented_by: Ref[];
  cypher: CypherCall[];
}

export interface CypherCall {
  name: string;
  params: Record<string, unknown>;
  rows: number;
  text?: string | null;
}

export type EvidenceStep =
  | {
      role: "decision";
      id: string;
      title: string;
      status: DecisionStatus;
      valid_from_iso: string;
      valid_to_iso: string | null;
    }
  | { role: "discussion"; id: string; title: string; url?: string | null; excerpt?: string | null }
  | { role: "incident"; id: string; title: string; url?: string | null }
  | { role: "person"; id: string; name: string; why?: string | null }
  | { role: "date"; iso: string };

export interface Supersession {
  newer: string;
  older: string;
  at_iso: string;
  signal: string;
  older_text: string;
  newer_text: string;
}

export interface Citation {
  kind: CitationKind | string;
  title: string;
  url?: string | null;
  excerpt?: string | null;
}

export interface SubgraphNode {
  id: string;
  label: string;
  props: Record<string, unknown>;
}

export interface SubgraphEdge {
  from: string;
  to: string;
  type: string;
}

export interface Subgraph {
  nodes: SubgraphNode[];
  edges: SubgraphEdge[];
}

export interface Why {
  route: string;
  cypher: CypherCall[];
  subgraph: Subgraph;
  llm: { backend: string; model: string; used: boolean };
}

export interface BaselineChunk {
  id: string;
  text: string;
  source_kind: string;
  score: number;
}

export interface Baseline {
  answer: string;
  chunks: BaselineChunk[];
  note: string;
}

export type AskMode = "graph" | "baseline" | "both";

export interface AskRequest {
  question: string;
  repo: string;
  at: string | null;
  mode: AskMode;
}

export interface AskResponse {
  question: string;
  repo: string;
  mode: AskMode;
  answer: string;
  refused: boolean;
  confidence: { score: number; label: "high" | "medium" | "low" | string; reasons: string[] };
  evidence_chain: EvidenceStep[];
  supersession: Supersession[];
  citations: Record<string, Citation>;
  entities: EntityRef[];
  why: Why;
  baseline: Baseline | null;
  /** Present on refusals: the closest entities and the person to ask. */
  closest?: EntityRef[];
  ask?: PersonCard | null;
}

export interface Timeline {
  at_iso: string;
  active: DecisionCard[];
  superseded_since: DecisionCard[];
  /** First and last decision dates in the repository; the slider spans them. */
  earliest_iso?: string | null;
  latest_iso?: string | null;
}

export interface Utterance {
  id: string;
  meeting_id: string;
  seq: number;
  text: string;
  text_en: string | null;
  start_ms: number;
  end_ms: number;
  speaker_label: string;
  speaker?: PersonCard | null;
  language: string;
  mentions?: EntityRef[];
}

export interface MeetingSummary {
  id: string;
  repo: string;
  title: string;
  started_at_iso: string;
  duration_ms: number;
  language: string;
  source: string;
  audio_uri: string | null;
  summary: string | null;
  utterance_count: number;
  decision_count: number;
}

export interface MeetingDetail extends MeetingSummary {
  utterances: Utterance[];
  decisions: DecisionCard[];
  speakers: { label: string; person: PersonCard | null }[];
}
