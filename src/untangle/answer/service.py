"""The answer service: `ask()` runs route -> gather -> confidence -> compose and assembles the `AskResponse`
(CONTRACTS §6); the other functions back the remaining API endpoints (`why_path`, `entity`, `search`, `timeline`,
`repos`, `health`). The HTTP layer and the CLI are thin wrappers over this module."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from untangle import __version__
from untangle.answer import baseline as baseline_mod
from untangle.answer.compose import CITATION, compose
from untangle.answer.confidence import score, signals_from
from untangle.answer.models import (
    AskResponse,
    Citation,
    CommitCard,
    Confidence,
    DecisionCard,
    EntityHit,
    EntityRef,
    EntityResponse,
    EvidenceStep,
    LLMInfo,
    PersonCard,
    PersonHit,
    PulseResponse,
    Ref,
    RepoInfo,
    SearchResponse,
    Subgraph,
    Supersession,
    TimelineResponse,
    Why,
    WhyPath,
)
from untangle.answer.retrieve import (
    Evidence,
    Recorder,
    Version,
    dotted_key,
    gather,
    person_from_row,
    ref_title,
    version_from_row,
    why_path_rows,
)
from untangle.answer.router import resolve_entities, resolve_people, route
from untangle.answer.text import iso, label_of, parse_at
from untangle.config import settings
from untangle.embed import Embedder, make_embedder
from untangle.graph.db import Graph, connect
from untangle.llm import LLM, make_llm

log = logging.getLogger("untangle.answer.service")

_graph: Graph | None = None
_llm: LLM | None = None
_lock = threading.Lock()


def get_graph() -> Graph:
    """Process-wide graph handle (the driver pools connections). Raises `GraphUnavailable` when Neo4j is down."""
    global _graph
    with _lock:
        if _graph is None:
            _graph = connect(require=True)
        return _graph


def get_llm() -> LLM:
    global _llm
    with _lock:
        if _llm is None:
            _llm = make_llm()
        return _llm


def reset() -> None:
    """Drop cached handles (tests, reconfiguration)."""
    global _graph, _llm
    with _lock:
        if _graph is not None:
            _graph.close()
        _graph, _llm = None, None


class NotFound(LookupError):
    """A decision or entity id that is not in the graph."""


# ------------------------------------------------------------------------------------------------------------------
# ask


def ask(
    question: str, repo: str, *, at: str | int | None = None, mode: str = "graph", graph: Graph | None = None,
    llm: LLM | None = None, embedder: Embedder | None = None, now_ms: int | None = None,
) -> AskResponse:
    """Answer `question` about `repo`. `at` (ISO date) answers as of that date; `mode` is graph, baseline or both."""
    if mode not in ("graph", "baseline", "both"):
        raise ValueError(f"mode must be graph, baseline or both, not {mode!r}")
    graph = graph or get_graph()
    llm = llm if llm is not None else get_llm()
    started = time.perf_counter()
    decision = route(question, at=at)
    at_ms = decision.at_ms if decision.intent == "belief_at" else None
    recorder = Recorder(graph)

    if mode == "baseline":
        base = baseline_mod.baseline(graph, repo, question, llm=llm, embedder=embedder, recorder=recorder)
        return AskResponse(
            question=question, repo=repo, mode=mode, answer=base.answer, refused=not base.chunks,
            confidence=Confidence(score=0.0, label="low", reasons=["vector-only baseline: no graph signals"]),
            why=Why(route="baseline", cypher=recorder.calls, subgraph=Subgraph(), llm=LLMInfo(backend=llm.backend, model=llm.model, used=llm.available)),
            baseline=base, at_iso=iso(at_ms), intent=decision.intent,
        )

    evidence = gather(graph, repo, decision, now_ms=now_ms, recorder=recorder)
    confidence = score(signals_from(evidence, at_ms=at_ms, now_ms=now_ms))
    composed = compose(evidence, confidence, llm, at_ms=at_ms)
    refused = confidence.label == "refuse"
    base = baseline_mod.baseline(graph, repo, question, llm=llm, embedder=embedder, recorder=recorder) if mode == "both" else None
    response = AskResponse(
        question=question, repo=repo, mode=mode, answer=composed.answer, refused=refused, confidence=confidence,
        evidence_chain=[] if refused else evidence_chain(evidence, at_ms),
        supersession=supersessions(evidence, at_ms=at_ms),
        citations=citations_for(composed.answer, evidence),
        # what the answer is about; when it refuses, the closest related entities instead
        entities=[EntityRef(id=e.id, label=e.label, name=e.name, path=e.path, key=e.key) for e in (evidence.related if refused else evidence.entities)],
        why=Why(
            route="refuse" if refused else evidence.route, cypher=recorder.calls,
            subgraph=Subgraph.model_validate(evidence.subgraph),
            llm=LLMInfo(backend=llm.backend, model=llm.model, used=composed.used_llm),
        ),
        baseline=base, at_iso=iso(at_ms), intent=decision.intent,
    )
    log.info("ask repo=%s intent=%s refused=%s confidence=%.2f llm=%s in %.0f ms", repo, decision.intent, refused, confidence.score, composed.used_llm, (time.perf_counter() - started) * 1000)
    return response


def evidence_chain(evidence: Evidence, at_ms: int | None) -> list[EvidenceStep]:
    """decision -> discussion -> incident -> commit -> person -> date, from the leading decision (or the fallback PRs)."""
    steps: list[EvidenceStep] = []
    led = evidence.lead(at_ms)
    if led is not None:
        v = led[1]
        steps.append(EvidenceStep(role="decision", id=v.id, title=v.text or v.subject, status=v.status, valid_from_iso=iso(v.valid_from), valid_to_iso=iso(v.valid_to)))
        seen = {v.id}
        for ref in [v.where, *v.evidence]:
            if not ref or not ref.get("id") or ref["id"] in seen or len(steps) > 5:
                continue
            seen.add(ref["id"])
            steps.append(EvidenceStep(role="discussion", id=ref["id"], title=ref_title(ref), url=ref.get("url"), excerpt=_excerpt(ref)))
        for issue in v.motivated_by:
            if issue.get("id") in seen:
                continue
            seen.add(issue["id"])
            steps.append(EvidenceStep(role="incident" if issue.get("is_incident") else "discussion", id=issue["id"], title=ref_title(issue), url=issue.get("url"), excerpt=_excerpt(issue)))
        spoken = evidence.spoken(v)
        if spoken and spoken[1].get("id") and spoken[1]["id"] not in seen:
            relation, k = spoken
            seen.add(k["id"])
            lead_in = "Handover call contradicts this" if relation == "contradicts" else "Handover call confirms this"
            steps.append(EvidenceStep(role="discussion", id=k["id"], title=f"{lead_in}: {k.get('object')}", excerpt=k.get("rationale") or k.get("text")))
        for c in v.implemented_by[:2]:
            if c.get("id") in seen:
                continue
            seen.add(c["id"])
            steps.append(EvidenceStep(role="commit", id=c["id"], title=ref_title(c), url=c.get("url"), excerpt=_excerpt(c)))
        person = _person_step(evidence, v)
        if person:
            steps.append(person)
        steps.append(EvidenceStep(role="date", iso=iso(v.valid_from)))
        return steps
    for pr in evidence.prs[:2]:
        steps.append(EvidenceStep(role="discussion", id=pr["id"], title=f"PR #{pr.get('number')} {pr.get('title') or ''}".strip(), url=pr.get("url"), excerpt=_excerpt(pr)))
        for issue in pr.get("closes") or []:
            steps.append(EvidenceStep(role="incident" if issue.get("is_incident") else "discussion", id=issue["id"], title=f"issue #{issue.get('number')} {issue.get('title') or ''}".strip(), url=issue.get("url")))
    for c in evidence.commits[:2]:
        steps.append(EvidenceStep(role="commit", id=c["id"], title=f"commit {(c.get('sha') or '')[:7]} {c.get('title') or ''}".strip(), url=c.get("url"), excerpt=_excerpt(c)))
    person = _person_step(evidence, None)
    if person:
        steps.append(person)
    stamp = (evidence.prs[0].get("merged_at") if evidence.prs else None) or (evidence.commits[0].get("authored_at") if evidence.commits else None)
    if stamp:
        steps.append(EvidenceStep(role="date", iso=iso(stamp)))
    return steps


def _excerpt(ref: dict[str, Any]) -> str | None:
    text = ref.get("excerpt")
    return text if text else None


def _person_step(evidence: Evidence, v: Version | None) -> EvidenceStep | None:
    stated = (v.stated_by or {}) if v else {}
    for p in evidence.people:
        if stated.get("id") == p.id:
            return EvidenceStep(role="person", id=p.id, name=p.display, why="stated the decision and " + p.why(evidence.entity_short))
    if stated.get("id"):
        return EvidenceStep(role="person", id=stated["id"], name=stated.get("name") or stated.get("login"), why="stated the decision")
    if evidence.people:
        p = evidence.people[0]
        return EvidenceStep(role="person", id=p.id, name=p.display, why=p.why(evidence.entity_short))
    if v is not None and v.who:
        return EvidenceStep(role="person", name=v.who, why="authored the source the decision was taken from")
    return None


def supersessions(evidence: Evidence, at_ms: int | None = None) -> list[Supersession]:
    """Replacements in the history the answer is about: the leading decision's chain, the same key in other files,
    and decisions about the entities the question matched. Unrelated chains that full-text search touched are left
    out: a list of every change in the evidence would bury the one that matters."""
    out: list[Supersession] = []
    seen: set[tuple[str, str]] = set()
    led = evidence.lead(at_ms)
    lead_ids = set(led[0].ids()) if led else set()
    lead_key = dotted_key(led[1]) if led else None
    entity_ids = {e.id for e in evidence.entities}
    subject_specific = bool(evidence.named_subject_terms())

    def relevant(v: Version) -> bool:
        if not led:
            return not subject_specific
        if subject_specific:
            return v.id in lead_ids or (lead_key is not None and dotted_key(v) == lead_key)
        return v.id in lead_ids or (lead_key is not None and dotted_key(v) == lead_key) or any(a.get("id") in entity_ids for a in v.about)

    for v in evidence.versions:
        if not relevant(v):
            continue
        for sb in v.superseded_by:
            key = (sb.get("id") or "", v.id)
            if not sb.get("id") or key in seen:
                continue
            seen.add(key)
            newer = evidence.version(sb["id"])
            # business time first (when the old value stopped applying); the edge's `at` is only when ingestion noticed
            out.append(Supersession(newer=sb["id"], older=v.id, at_iso=iso(v.valid_to) or iso(sb.get("at")), signal=sb.get("signal"), older_text=v.text, newer_text=newer.text if newer else None))
    out.sort(key=lambda s: s.at_iso or "", reverse=True)
    return out


def citations_for(answer: str, evidence: Evidence) -> dict[str, Citation]:
    citable = evidence.citable()
    return {cid: citable[cid] for cid in dict.fromkeys(CITATION.findall(answer)) if cid in citable}


# ------------------------------------------------------------------------------------------------------------------
# cards


def decision_card(v: Version) -> DecisionCard:
    return DecisionCard(
        id=v.id, kind=v.kind, key=v.key, subject=v.subject, predicate=v.predicate, object=v.object, text=v.text,
        rationale=v.rationale, status=v.status, valid_from_iso=iso(v.valid_from), valid_to_iso=iso(v.valid_to),
        confidence=v.confidence, signal=v.signal,
        about=[EntityRef(id=a["id"], label=label_of(a.get("id"), a.get("labels")), name=a.get("name"), path=a.get("path"), key=a.get("key")) for a in v.about if a.get("id")],
        decided_in=ref_card(v.decided_in) if v.decided_in else None,
        stated_by=PersonCard(id=v.stated_by["id"], name=v.stated_by.get("name"), login=v.stated_by.get("login")) if v.stated_by and v.stated_by.get("id") else None,
    )


def ref_card(ref: dict[str, Any]) -> Ref:
    return Ref(
        id=ref["id"], kind=label_of(ref.get("id"), ref.get("labels")), title=ref.get("title") or ref_title(ref), url=ref.get("url"),
        number=ref.get("number"), created_at_iso=iso(ref.get("created_at")), excerpt=ref.get("excerpt") or None, author=ref.get("author"),
    )


def person_card(row: dict[str, Any], what: str = "it") -> PersonCard:
    p = person_from_row(row)
    return PersonCard(id=p.id, name=p.name, login=p.login, why=p.why(what), score=round(p.score, 3))


def commit_card(c: dict[str, Any]) -> CommitCard:
    author = c.get("author") or {}
    pr = c.get("pr") or {}
    return CommitCard(
        id=c["id"], sha=c.get("sha"), title=c.get("title"), url=c.get("url"), authored_at_iso=iso(c.get("authored_at")),
        author=PersonCard(id=author["id"], name=author.get("name"), login=author.get("login")) if author.get("id") else None,
        pr=Ref(id=pr["id"], kind="PullRequest", title=pr.get("title"), url=pr.get("url"), number=pr.get("number")) if pr.get("id") else None,
        paths=list(c.get("paths") or []),
    )


# ------------------------------------------------------------------------------------------------------------------
# other endpoints


def why_path(decision_id: str, *, graph: Graph | None = None) -> WhyPath:
    graph = graph or get_graph()
    root, others, rec = why_path_rows(graph, decision_id)
    if root is None:
        raise NotFound(f"no decision {decision_id!r}")
    older = [v for v in others if (v.valid_from or 0) <= (root.valid_from or 0)]
    newer = [v for v in others if (v.valid_from or 0) > (root.valid_from or 0)]
    evidence = [e for e in root.evidence if e.get("id")]
    if not evidence and root.decided_in and root.decided_in.get("id"):
        # config and dependency decisions are evidenced by the commit or PR that made them
        evidence = [root.decided_in]
    return WhyPath(
        decision=decision_card(root),
        evidence=[ref_card(e) for e in evidence],
        older=[decision_card(v) for v in older], newer=[decision_card(v) for v in newer],
        motivated_by=[ref_card(i) for i in root.motivated_by if i.get("id")],
        implemented_by=[ref_card(c) for c in root.implemented_by if c.get("id")],
        cypher=rec.calls,
    )


def entity(entity_id: str, *, graph: Graph | None = None, now_ms: int | None = None) -> EntityResponse:
    graph = graph or get_graph()
    rec = Recorder(graph)
    rows = rec.run("entity_by_id", {"id": entity_id})
    if not rows:
        raise NotFound(f"no entity {entity_id!r}")
    node = {k: v for k, v in rows[0].items() if v is not None}
    for key in ("current_since", "first_seen_at", "last_touched_at"):
        if key in node:
            node[f"{key}_iso"] = iso(node[key])
    repo = entity_id.split(":", 2)[1] if entity_id.count(":") >= 2 else ""
    seen: set[str] = set()
    decisions: list[DecisionCard] = []
    for row in rec.run("decisions_about", {"repo": repo, "ids": [entity_id], "terms": [], "limit": 12, "chain_limit": 40}):
        if row["id"] not in seen:
            seen.add(row["id"])
            decisions.append(decision_card(version_from_row(row)))
    what = node.get("key") or node.get("name") or "it"
    people = [person_card(r, what) for r in rec.run("person_to_ask", {"repo": repo, "ids": [entity_id], "now": now_ms or int(time.time() * 1000), "limit": 3})]
    commits = [commit_card(c) for c in rec.run("recent_commits_about", {"ids": [entity_id], "limit": 10})]
    return EntityResponse(entity=node, decisions=decisions, people=people, recent_commits=commits)


def search(repo: str, q: str, *, graph: Graph | None = None) -> SearchResponse:
    graph = graph or get_graph()
    rec = Recorder(graph)
    decision = route(q)
    hits = resolve_entities(rec, repo, decision, limit=10, threshold=0.0, candidates=20) if (decision.terms or decision.mentions) else []
    top = max((h.lucene_score for h in hits), default=0.0) or 1.0
    entities = [
        EntityHit(id=h.id, label=h.label, name=h.name, path=h.path, key=h.key, score=round(max(h.strength, 0.3 * h.lucene_score / top), 3))
        for h in hits
    ]
    entities.sort(key=lambda h: h.score, reverse=True)
    people = [PersonHit(id=r["id"], name=r.get("name"), login=r.get("login"), score=round(float(r.get("score") or 0.0), 3)) for r in resolve_people(rec, repo, q)]
    return SearchResponse(entities=entities[:10], people=people)


def timeline(repo: str, at: str | int | None, *, graph: Graph | None = None) -> TimelineResponse:
    graph = graph or get_graph()
    at_ms = parse_at(at) if at not in (None, "") else int(time.time() * 1000)
    rec = Recorder(graph)
    rows = rec.run("belief_at", {"repo": repo, "t": at_ms, "ids": [], "limit": 100})
    bounds = (rec.run("decision_bounds", {"repo": repo}) or [{}])[0]
    active = [decision_card(version_from_row(r)) for r in rows if r.get("in_force")]
    superseded = [decision_card(version_from_row(r)) for r in rows if r.get("superseded_since")]
    return TimelineResponse(
        at_iso=iso(at_ms) or "", active=active, superseded_since=superseded,
        earliest_iso=iso(bounds.get("earliest")), latest_iso=iso(bounds.get("latest")),
    )


def pulse(repo: str, *, graph: Graph | None = None, now_ms: int | None = None, limit: int = 24) -> PulseResponse:
    """Return deterministic knowledge risks for a repository."""
    from untangle.pulse import build_response

    graph = graph or get_graph()
    now = now_ms or int(time.time() * 1000)
    bounded_limit = max(1, min(int(limit), 50))
    stale_before = now - 365 * 86_400_000
    owner_stale_before = now - 540 * 86_400_000
    rows = Recorder(graph).run(
        "pulse",
        {"repo": repo, "now": now, "stale_before": stale_before, "owner_stale_before": owner_stale_before, "limit": bounded_limit},
    )
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                **row,
                "decision": {
                    "id": row.get("decision_id"), "kind": row.get("decision_kind"), "key": row.get("decision_key"),
                    "subject": row.get("decision_subject"), "predicate": row.get("decision_predicate"),
                    "object": row.get("decision_object"), "text": row.get("decision_text"),
                    "rationale": row.get("decision_rationale"), "status": row.get("decision_status"),
                    "valid_from": row.get("decision_valid_from"), "valid_to": row.get("decision_valid_to"),
                    "created_at": row.get("decision_created_at"), "confidence": row.get("decision_confidence"),
                    "signal": row.get("decision_signal"), "about": row.get("about") or [],
                    "stated_by": row.get("stated_by"), "decided_in": row.get("decided_in"),
                    "motivated_by": row.get("motivated_by") or [], "implemented_by": row.get("implemented_by") or [],
                    "evidence": row.get("evidence") or [], "supersedes": [], "superseded_by": [],
                },
                "owner_last_active": row.get("owner_last_active"), "last_touched": row.get("last_touched"),
            }
        )
    return build_response(rows=normalized, repo=repo, generated_at_iso=iso(now) or "", limit=bounded_limit)


def repos(*, graph: Graph | None = None) -> list[RepoInfo]:
    graph = graph or get_graph()
    out: list[RepoInfo] = []
    for r in Recorder(graph).run("repos", {}):
        out.append(
            RepoInfo(
                full_name=r.get("full_name") or (r.get("id") or "").removeprefix("repo:"), url=r.get("url"), head_sha=r.get("head_sha"),
                commit_count=r.get("commit_count"), ingested_at_iso=iso(r.get("ingested_at")),
                counts={k: int(r.get(k) or 0) for k in ("commits", "prs", "issues", "decisions", "meetings")},
            )
        )
    return out


def health(*, graph: Graph | None = None) -> dict[str, Any]:
    s = settings()
    neo4j: dict[str, Any] = {"ok": False, "version": None, "aura": s.aura, "uri": s.neo4j_uri}
    ok = False
    try:
        g = graph or get_graph()
        ok = g.ping()
        if ok:
            caps = g.capabilities()
            neo4j.update(ok=True, version=caps.get("version"), aura=bool(caps.get("aura")), edition=caps.get("edition"))
    except Exception as exc:  # noqa: BLE001 - health must answer even when the database is down
        neo4j["error"] = str(exc)[:200]
    llm = get_llm()
    try:
        emb = make_embedder()
        embedding = {"backend": emb.backend, "dim": emb.dim, "available": True}
    except Exception:  # noqa: BLE001 - readiness must report a failed model load
        log.exception("embedding backend is unavailable")
        embedding = {"backend": s.embed_backend, "dim": s.embed_dim, "available": False}
        ok = False
    if s.llm_backend != "fake" and not llm.available:
        ok = False
    return {
        "ok": ok, "version": __version__, "neo4j": neo4j,
        "llm": {"backend": llm.backend, "model": llm.model, "available": llm.available},
        "embed": embedding,
        "sarvam": {"configured": bool(s.sarvam_api_key), "model": s.sarvam_stt_model},
    }


__all__ = [
    "NotFound", "ask", "citations_for", "decision_card", "entity", "evidence_chain", "get_graph", "get_llm", "health",
    "pulse", "repos", "reset", "search", "supersessions", "timeline", "why_path",
]
