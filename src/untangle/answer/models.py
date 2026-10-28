"""Pydantic models for the answer service and the HTTP API, matching `docs/CONTRACTS.md` §6 field for field.
Timestamps are rendered as `*_iso` strings here; the graph keeps epoch milliseconds."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

Mode = Literal["graph", "baseline", "both"]
Intent = Literal["why", "who_to_ask", "what_changed", "belief_at", "is_current", "list_decisions"]


class Confidence(BaseModel):
    score: float
    label: Literal["high", "medium", "low", "refuse"]
    reasons: list[str] = Field(default_factory=list)


class EvidenceStep(BaseModel):
    """One link of the evidence chain. Keys differ by role (decision, discussion, incident, commit, person, date)."""

    role: Literal["decision", "discussion", "incident", "commit", "person", "entity", "date"]
    id: str | None = None
    title: str | None = None
    status: str | None = None
    valid_from_iso: str | None = None
    valid_to_iso: str | None = None
    url: str | None = None
    excerpt: str | None = None
    name: str | None = None
    why: str | None = None
    iso: str | None = None


class Supersession(BaseModel):
    newer: str
    older: str
    at_iso: str | None = None
    signal: str | None = None
    older_text: str | None = None
    newer_text: str | None = None


class Citation(BaseModel):
    kind: str
    title: str | None = None
    url: str | None = None
    excerpt: str | None = None


class EntityRef(BaseModel):
    id: str
    label: str
    name: str | None = None
    path: str | None = None
    key: str | None = None


class CypherCall(BaseModel):
    name: str
    params: dict[str, Any]
    rows: int
    ms: float | None = None


class SubgraphNode(BaseModel):
    id: str
    label: str
    props: dict[str, Any] = Field(default_factory=dict)


class SubgraphEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    type: str


class Subgraph(BaseModel):
    nodes: list[SubgraphNode] = Field(default_factory=list)
    edges: list[SubgraphEdge] = Field(default_factory=list)


class LLMInfo(BaseModel):
    backend: str
    model: str
    used: bool


class Why(BaseModel):
    route: str
    cypher: list[CypherCall] = Field(default_factory=list)
    subgraph: Subgraph = Field(default_factory=Subgraph)
    llm: LLMInfo


class BaselineChunk(BaseModel):
    id: str
    text: str
    source_kind: str | None = None
    score: float
    source_id: str | None = None


class Baseline(BaseModel):
    answer: str
    chunks: list[BaselineChunk] = Field(default_factory=list)
    note: str


class AskResponse(BaseModel):
    question: str
    repo: str
    mode: Mode
    answer: str
    refused: bool
    confidence: Confidence
    evidence_chain: list[EvidenceStep] = Field(default_factory=list)
    supersession: list[Supersession] = Field(default_factory=list)
    citations: dict[str, Citation] = Field(default_factory=dict)
    entities: list[EntityRef] = Field(default_factory=list)
    why: Why
    baseline: Baseline | None = None
    at_iso: str | None = None
    intent: Intent = "why"


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    repo: str = Field(min_length=3)
    at: str | None = None
    mode: Mode = "graph"


class PulseSummary(BaseModel):
    active_decisions: int = 0
    risks: int = 0
    critical: int = 0
    coverage: float = 1.0
    contradictions: int = 0
    drift: int = 0
    ownership_gaps: int = 0


class PulseRisk(BaseModel):
    id: str
    category: Literal["contradiction", "drift", "ownership_gap", "rationale_gap", "stale"]
    score: float
    reasons: list[str] = Field(default_factory=list)
    entity: EntityRef
    decision: DecisionCard
    owner: PersonCard | None = None
    evidence: list[Ref] = Field(default_factory=list)
    contradictions: list[Ref] = Field(default_factory=list)
    last_touched_iso: str | None = None
    owner_last_active_iso: str | None = None


class PulseResponse(BaseModel):
    repo: str
    generated_at_iso: str
    summary: PulseSummary
    risks: list[PulseRisk] = Field(default_factory=list)


class PersonCard(BaseModel):
    id: str
    name: str | None = None
    login: str | None = None
    why: str | None = None
    score: float | None = None


class Ref(BaseModel):
    id: str
    kind: str
    title: str | None = None
    url: str | None = None
    number: int | None = None
    created_at_iso: str | None = None
    excerpt: str | None = None
    author: str | None = None

    @computed_field  # the web app reads the date as `at_iso`; keep both names so neither side has to guess
    @property
    def at_iso(self) -> str | None:
        return self.created_at_iso


class DecisionCard(BaseModel):
    id: str
    kind: str | None = None
    key: str | None = None
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    text: str | None = None
    rationale: str | None = None
    status: str | None = None
    valid_from_iso: str | None = None
    valid_to_iso: str | None = None
    confidence: float | None = None
    signal: str | None = None
    about: list[EntityRef] = Field(default_factory=list)
    decided_in: Ref | None = None
    stated_by: PersonCard | None = None


class WhyPath(BaseModel):
    decision: DecisionCard
    evidence: list[Ref] = Field(default_factory=list)
    older: list[DecisionCard] = Field(default_factory=list)
    newer: list[DecisionCard] = Field(default_factory=list)
    motivated_by: list[Ref] = Field(default_factory=list)
    implemented_by: list[Ref] = Field(default_factory=list)
    cypher: list[CypherCall] = Field(default_factory=list)


class EntityHit(BaseModel):
    id: str
    label: str
    name: str | None = None
    path: str | None = None
    key: str | None = None
    score: float


class PersonHit(BaseModel):
    id: str
    name: str | None = None
    login: str | None = None
    score: float


class SearchResponse(BaseModel):
    entities: list[EntityHit] = Field(default_factory=list)
    people: list[PersonHit] = Field(default_factory=list)


class TimelineResponse(BaseModel):
    at_iso: str
    active: list[DecisionCard] = Field(default_factory=list)
    superseded_since: list[DecisionCard] = Field(default_factory=list)
    earliest_iso: str | None = None  # first decision in the repository (the slider's start)
    latest_iso: str | None = None


class CommitCard(BaseModel):
    id: str
    sha: str | None = None
    title: str | None = None
    url: str | None = None
    authored_at_iso: str | None = None
    author: PersonCard | None = None
    pr: Ref | None = None
    paths: list[str] = Field(default_factory=list)


class EntityResponse(BaseModel):
    entity: dict[str, Any]
    decisions: list[DecisionCard] = Field(default_factory=list)
    people: list[PersonCard] = Field(default_factory=list)
    recent_commits: list[CommitCard] = Field(default_factory=list)


class RepoInfo(BaseModel):
    full_name: str
    url: str | None = None
    head_sha: str | None = None
    commit_count: int | None = None
    ingested_at_iso: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
