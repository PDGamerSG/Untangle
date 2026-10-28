"""Evidence gathering. Runs the `cypher/3x_*` retrieval statements, records every call for the "Why this answer"
panel, and folds decision rows into **dossiers**: one per SUPERSEDES chain, versions oldest to newest, each version
carrying who stated it, where it was decided, its evidence excerpts and incident links.

Decisions found by entity (`31_decisions_about`), by reference (`31_decisions_for_ref`) and by full text
(`35_decision_search`) are merged with reciprocal rank fusion. When no decision exists, merged PRs and recent commits
on the entity's files are the fallback evidence."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from untangle.answer.models import Citation, CypherCall
from untangle.answer.router import ResolvedEntity, RouterDecision, resolve_entities, scrub_repo_terms, specific_terms
from untangle.answer.text import date_forms, fmt_date, kind_of_id, label_of, short_sha, squash
from untangle.graph.db import Graph
from untangle.ids import commit_id, issue_id, pr_id, tokens

log = logging.getLogger("untangle.answer.retrieve")

READ_TIMEOUT_MS = 2000
RRF_K = 60
MAX_DOSSIERS = 8
MAX_VERSIONS_PER_DOSSIER = 12


class Recorder:
    """Runs named read queries with a timeout and keeps `(name, params, rows, ms)` for the Why panel."""

    def __init__(self, graph: Graph, *, timeout_ms: int = READ_TIMEOUT_MS):
        self.graph = graph
        self.timeout_ms = timeout_ms
        self.calls: list[CypherCall] = []

    def run(self, name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        started = time.perf_counter()
        result = self.graph.run_named(name, params, timeout=self.timeout_ms)
        rows = result.records
        ms = round((time.perf_counter() - started) * 1000.0, 1)
        self.calls.append(CypherCall(name=_file_name(name), params=_loggable(params), rows=len(rows), ms=ms))
        log.debug("%s %s -> %d rows in %.1f ms", name, _loggable(params), len(rows), ms)
        return rows


def _file_name(name: str) -> str:
    from untangle.graph.queries import cypher_path

    try:
        return cypher_path(name).stem
    except FileNotFoundError:  # pragma: no cover
        return name


def _loggable(params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(v, list) and v and isinstance(v[0], float):
            out[k] = f"<vector dim={len(v)}>"
        elif isinstance(v, list) and len(v) > 12:
            out[k] = v[:12] + [f"... +{len(v) - 12}"]
        else:
            out[k] = v
    return out


# ------------------------------------------------------------------------------------------------------------------
# Dossiers


@dataclass
class Version:
    """One Decision node with everything `31`/`32`/`33`/`35` project for it."""

    id: str
    kind: str | None
    key: str | None
    subject: str | None
    predicate: str | None
    object: str | None
    text: str | None
    rationale: str | None
    status: str | None
    valid_from: int | None
    valid_to: int | None
    created_at: int | None
    confidence: float | None
    signal: str | None
    about: list[dict[str, Any]] = field(default_factory=list)
    stated_by: dict[str, Any] | None = None
    decided_in: dict[str, Any] | None = None
    motivated_by: list[dict[str, Any]] = field(default_factory=list)
    implemented_by: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    superseded_by: list[dict[str, Any]] = field(default_factory=list)
    # spoken (KT) statements vs the repository record: 24_reconcile_kt writes CONFIRMS / CONTRADICTS
    confirms: list[dict[str, Any]] = field(default_factory=list)
    contradicts: list[dict[str, Any]] = field(default_factory=list)
    confirmed_by: list[dict[str, Any]] = field(default_factory=list)
    contradicted_by: list[dict[str, Any]] = field(default_factory=list)
    score: float = 0.0  # fusion score
    in_force: bool | None = None  # from 33_belief_at

    @property
    def active(self) -> bool:
        return self.status == "active"

    @property
    def where(self) -> dict[str, Any] | None:
        """Where it was decided: DECIDED_IN, else the first implementing commit, else the first evidence node."""
        if self.decided_in:
            return self.decided_in
        if self.implemented_by:
            return self.implemented_by[0]
        if self.evidence:
            return self.evidence[0]
        return None

    @property
    def who(self) -> str | None:
        if self.stated_by and self.stated_by.get("name"):
            return self.stated_by["name"]
        where = self.where
        if where and where.get("author"):
            return where["author"]
        for ev in self.evidence:
            if ev.get("author"):
                return ev["author"]
        return None

    @property
    def incidents(self) -> list[dict[str, Any]]:
        return [i for i in self.motivated_by if i.get("is_incident")]

    @property
    def ref_ids(self) -> list[str]:
        """Every graph node this version points at (for citations and subgraph seeds)."""
        ids = [self.id]
        for ref in [self.decided_in, self.stated_by, *self.motivated_by, *self.implemented_by, *self.evidence]:
            if ref and ref.get("id"):
                ids.append(ref["id"])
        return list(dict.fromkeys(ids))

    def in_force_at(self, t: int) -> bool:
        if self.valid_from is None or self.valid_from > t:
            return False
        return self.valid_to is None or self.valid_to > t


def version_from_row(row: dict[str, Any]) -> Version:
    return Version(
        id=row["id"], kind=row.get("kind"), key=row.get("key"), subject=row.get("subject"), predicate=row.get("predicate"),
        object=_str(row.get("object")), text=row.get("text"), rationale=row.get("rationale"), status=row.get("status"),
        valid_from=row.get("valid_from"), valid_to=row.get("valid_to"), created_at=row.get("created_at"),
        confidence=row.get("confidence"), signal=row.get("signal"), about=list(row.get("about") or []),
        stated_by=row.get("stated_by"), decided_in=row.get("decided_in"), motivated_by=list(row.get("motivated_by") or []),
        implemented_by=list(row.get("implemented_by") or []), evidence=list(row.get("evidence") or []),
        supersedes=list(row.get("supersedes") or []), superseded_by=list(row.get("superseded_by") or []),
        confirms=list(row.get("confirms") or []), contradicts=list(row.get("contradicts") or []),
        confirmed_by=list(row.get("confirmed_by") or []), contradicted_by=list(row.get("contradicted_by") or []),
        in_force=row.get("in_force"),
    )


def _str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


@dataclass
class Dossier:
    """One SUPERSEDES chain, oldest version first."""

    versions: list[Version]
    score: float = 0.0

    @property
    def top(self) -> Version:
        """The version an answer leads with: the active one, else the newest."""
        for v in reversed(self.versions):
            if v.active:
                return v
        return self.versions[-1]

    @property
    def newest(self) -> Version:
        return self.versions[-1]

    @property
    def oldest(self) -> Version:
        return self.versions[0]

    @property
    def subject(self) -> str | None:
        return self.top.subject

    @property
    def key(self) -> str | None:
        return self.top.key

    def at(self, t: int) -> Version | None:
        for v in reversed(self.versions):
            if v.in_force_at(t):
                return v
        return None

    def ids(self) -> list[str]:
        return [v.id for v in self.versions]


def build_dossiers(versions: dict[str, Version]) -> list[Dossier]:
    """Group versions into chains with union-find over SUPERSEDES edges (both directions, including edges to
    versions that were not returned: they are simply absent). Sorted best first by the best version's fusion
    score (a long chain is a little more interesting, not proportionally so)."""
    parent: dict[str, str] = {vid: vid for vid in versions}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for v in versions.values():
        for other in v.supersedes:
            if other in parent:
                union(v.id, other)
        for other in v.superseded_by:
            if other.get("id") in parent:
                union(v.id, other["id"])
    groups: dict[str, list[Version]] = {}
    for v in versions.values():
        groups.setdefault(find(v.id), []).append(v)
    dossiers: list[Dossier] = []
    for members in groups.values():
        members.sort(key=lambda v: (v.valid_from or 0, v.created_at or 0, v.id))
        members = members[-MAX_VERSIONS_PER_DOSSIER:]
        dossiers.append(Dossier(versions=members, score=max(v.score for v in members) + 0.001 * (len(members) - 1)))
    dossiers.sort(key=lambda d: (d.score, 1 if d.top.active else 0, d.top.valid_from or 0), reverse=True)
    return dossiers


def dotted_key(v: Version) -> str | None:
    """`app.concurrency` for a config decision whose subject is `schema.sql::app.concurrency`."""
    subject = v.subject or ""
    return subject.split("::", 1)[1] if "::" in subject else None


def is_removed(v: Version) -> bool:
    return (v.object or "").strip().lower() == "removed"


def demote_moved(dossiers: list[Dossier], mentioned: set[str] | None = None) -> list[Dossier]:
    """A setting that moved files (config.toml.sample -> schema.sql) leaves a chain ending in "removed". When a live
    record of the same key exists elsewhere, that chain is history, not the answer: it sorts after the live one,
    unless the question names that file ("why is concurrency 5 in config.toml.sample?" asks for exactly that history)."""
    mentioned = {m.lower() for m in mentioned or set()}
    live = {
        dotted_key(d.top) for d in dossiers
        if d.top.active and d.top.predicate == "config_value" and d.top.kind != "kt" and not is_removed(d.top) and dotted_key(d.top)
    }
    for d in dossiers:
        path = (d.top.subject or "").split("::", 1)[0].lower()
        named = path in mentioned or any(path.endswith("/" + m) for m in mentioned)
        if d.top.predicate == "config_value" and is_removed(d.top) and dotted_key(d.top) in live and not named:
            d.score -= 1.0
    dossiers.sort(key=lambda d: (d.score, 1 if d.top.active else 0, d.top.valid_from or 0), reverse=True)
    return dossiers


def moved_from(dossiers: list[Dossier], v: Version) -> Dossier | None:
    """The chain of the same key in another file that ends in "removed" (where the setting used to live)."""
    key = dotted_key(v)
    if not key or v.predicate != "config_value":
        return None
    for d in dossiers:
        t = d.top
        if t.id != v.id and dotted_key(t) == key and is_removed(t) and t.subject != v.subject and len(d.versions) > 1:
            return d
    return None


def moved_to(dossiers: list[Dossier], v: Version) -> Version | None:
    """For a key removed from one file, the live record of the same key in another file (where it lives now)."""
    key = dotted_key(v)
    if not key or not is_removed(v):
        return None
    for d in dossiers:
        t = d.top
        if t.id != v.id and dotted_key(t) == key and t.active and t.kind != "kt" and not is_removed(t) and t.subject != v.subject:
            return t
    return None


def rrf(rankings: list[list[str]], *, k: int = RRF_K) -> dict[str, float]:
    """Reciprocal rank fusion of several ranked id lists."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return scores


# ------------------------------------------------------------------------------------------------------------------
# People


@dataclass
class PersonToAsk:
    id: str
    name: str | None
    login: str | None
    score: float
    counts: dict[str, int]
    total_commits: int
    total_prs: int
    scope: str | None = None  # overrides `what` in `why()` (e.g. "this repository" for the repo-level fallback)

    @property
    def display(self) -> str:
        return self.name or self.login or self.id

    def why(self, what: str = "this file") -> str:
        """"authored 12 of 20 commits on this file, reviewed 4 PRs, stated 1 decision"."""
        what = self.scope or what
        bits: list[str] = []
        n = self.counts.get("commit", 0)
        if n:
            bits.append(f"authored {n} of {self.total_commits} commits on {what}" if self.total_commits else f"authored {n} commits on {what}")
        n = self.counts.get("review", 0)
        if n:
            bits.append(f"reviewed {n} of {self.total_prs} PRs touching it" if self.total_prs else f"reviewed {n} PRs touching it")
        n = self.counts.get("comment", 0)
        if n:
            bits.append(f"left {n} review comment{'s' if n != 1 else ''} on it")
        n = self.counts.get("decision", 0)
        if n:
            bits.append(f"stated {n} recorded decision{'s' if n != 1 else ''} about it")
        return ", ".join(bits) or "is linked to it in the graph"


def person_from_row(row: dict[str, Any], *, scope: str | None = None) -> PersonToAsk:
    counts = {p["kind"]: int(p["n"]) for p in row.get("parts") or []}
    return PersonToAsk(
        id=row["id"], name=row.get("name"), login=row.get("login"), score=float(row.get("score") or 0.0), counts=counts,
        total_commits=int(row.get("total_commits") or 0), total_prs=int(row.get("total_prs") or 0), scope=scope,
    )


# ------------------------------------------------------------------------------------------------------------------
# Evidence


@dataclass
class Evidence:
    repo: str
    question: str
    decision: RouterDecision
    entities: list[ResolvedEntity] = field(default_factory=list)  # matched
    related: list[ResolvedEntity] = field(default_factory=list)  # closest unmatched (for refusals)
    dossiers: list[Dossier] = field(default_factory=list)
    prs: list[dict[str, Any]] = field(default_factory=list)
    commits: list[dict[str, Any]] = field(default_factory=list)
    people: list[PersonToAsk] = field(default_factory=list)
    subgraph: dict[str, Any] = field(default_factory=lambda: {"nodes": [], "edges": []})
    calls: list[CypherCall] = field(default_factory=list)
    route: str = "entity_why"

    @property
    def versions(self) -> list[Version]:
        return [v for d in self.dossiers for v in d.versions]

    def version(self, decision_id: str) -> Version | None:
        for v in self.versions:
            if v.id == decision_id:
                return v
        return None

    @property
    def top(self) -> Dossier | None:
        return self.dossiers[0] if self.dossiers else None

    def lead(self, at_ms: int | None = None) -> tuple[Dossier, Version] | None:
        """The decision an answer leads with. Normally the top dossier's active (or in-force) version; when that is a
        spoken (KT) statement linked to a repository record, the repository record leads and the call supports or
        disputes it, so speech never reads as overriding what the code history says."""
        top = self.top
        if top is None:
            return None
        v = (top.at(at_ms) if at_ms is not None else None) or top.top
        if v.kind == "kt" and self.decision.source != "kt":  # asked what the call said: the call leads
            for partner in v.contradicts + v.confirms:
                pv = self.version(partner.get("id") or "")
                if pv is None:
                    continue
                for d in self.dossiers:
                    if pv.id in d.ids():
                        return d, pv
        return top, v

    def spoken(self, v: Version) -> tuple[str, dict[str, Any]] | None:
        """The handover-call statement that confirms or contradicts `v` (a repository decision), or `v`'s own
        partner when `v` is the spoken one: ('contradicts'|'confirms', projection)."""
        if v.contradicted_by:
            return "contradicts", v.contradicted_by[0]
        if v.confirmed_by:
            return "confirms", v.confirmed_by[0]
        return None

    @property
    def anchored(self) -> bool:
        """Something (a decision, a PR or a commit) is anchored on a resolved entity or reference."""
        if self.dossiers:
            return True
        return bool(self.entities) and bool(self.prs or self.commits)

    @property
    def entity_label(self) -> str:
        """What the question is about, for prose: `app.concurrency` in `config.toml`."""
        if self.entities:
            e = self.entities[0]
            if e.label == "ConfigKey" and e.key:
                return f"`{e.key}` in `{e.path}`" if e.path else f"`{e.key}`"
            return f"`{e.path or e.name or e.key}`"
        if self.dossiers and self.top:
            return f"`{self.top.subject}`" if self.top.subject else "that"
        return "that"

    @property
    def entity_short(self) -> str:
        if self.entities:
            e = self.entities[0]
            return e.key or e.name or e.path or e.id
        return "that"

    def citable(self) -> dict[str, Citation]:
        """Every id an answer may cite, with what the UI shows for it."""
        out: dict[str, Citation] = {}
        for v in self.versions:
            out[v.id] = Citation(
                kind="decision", title=v.text or v.subject, url=(v.where or {}).get("url"),
                excerpt=squash(v.rationale or v.text, 320),
            )
            for ref in [v.decided_in, *v.motivated_by, *v.implemented_by, *v.evidence]:
                if ref and ref.get("id") and ref["id"] not in out:
                    out[ref["id"]] = Citation(
                        kind=kind_of_id(ref["id"]), title=ref_title(ref), url=ref.get("url"), excerpt=squash(ref.get("excerpt"), 320)
                    )
            if v.stated_by and v.stated_by.get("id"):
                out.setdefault(v.stated_by["id"], Citation(kind="person", title=v.stated_by.get("name")))
        for pr in self.prs:
            out.setdefault(pr["id"], Citation(kind="pr", title=f"PR #{pr.get('number')} {pr.get('title') or ''}".strip(), url=pr.get("url"), excerpt=squash(pr.get("excerpt"), 320)))
            for issue in pr.get("closes") or []:
                out.setdefault(issue["id"], Citation(kind="issue", title=f"#{issue.get('number')} {issue.get('title') or ''}".strip(), url=issue.get("url")))
        for c in self.commits:
            out.setdefault(c["id"], Citation(kind="commit", title=f"{short_sha(c.get('sha'))} {c.get('title') or ''}".strip(), url=c.get("url"), excerpt=squash(c.get("excerpt"), 320)))
        for e in self.entities + self.related:
            out.setdefault(e.id, Citation(kind=e.label.lower(), title=e.display, excerpt=e.path))
        for p in self.people:
            out.setdefault(p.id, Citation(kind="person", title=p.display, excerpt=p.why(self.entity_short)))
        return out

    def grounding_corpus(self) -> dict[str, str]:
        """Per citable id: the text an answer's numbers and dates must come from."""
        corpus: dict[str, list[str]] = {}

        def add(node_id: str | None, *parts: Any) -> None:
            if not node_id:
                return
            bucket = corpus.setdefault(node_id, [])
            for part in parts:
                if part is None:
                    continue
                if isinstance(part, int | float) and not isinstance(part, bool):
                    bucket.append(str(part))
                elif isinstance(part, str):
                    bucket.append(part)

        for v in self.versions:
            add(v.id, v.text, v.object, v.rationale, v.subject, v.key, *date_forms(v.valid_from), *date_forms(v.valid_to))
            for ref in [v.decided_in, *v.motivated_by, *v.implemented_by, *v.evidence]:
                if not ref:
                    continue
                add(ref.get("id"), ref.get("title"), ref.get("excerpt"), ref.get("number"), ref.get("sha"), ref.get("url"), *date_forms(ref.get("created_at")))
                add(v.id, ref.get("title"), ref.get("number"), ref.get("sha"), *date_forms(ref.get("created_at")))  # the decision sentence may name its source
            if v.stated_by:
                add(v.stated_by.get("id"), v.stated_by.get("name"), v.stated_by.get("login"))
        for pr in self.prs:
            add(pr["id"], pr.get("title"), pr.get("excerpt"), pr.get("number"), pr.get("url"), *date_forms(pr.get("merged_at")), *date_forms(pr.get("created_at")))
            for issue in pr.get("closes") or []:
                add(issue["id"], issue.get("title"), issue.get("number"), issue.get("url"))
                add(pr["id"], issue.get("number"))
            for c in pr.get("commits") or []:
                add(pr["id"], c.get("sha"), c.get("title"))
        for c in self.commits:
            add(c["id"], c.get("sha"), c.get("title"), c.get("excerpt"), c.get("url"), *date_forms(c.get("authored_at")))
        for e in self.entities + self.related:
            add(e.id, e.name, e.path, e.key, e.extra.get("current_value"), e.extra.get("current_version"))
        for p in self.people:
            add(p.id, p.name, p.login, p.total_commits, p.total_prs, *p.counts.values())
        return {k: " ".join(v) for k, v in corpus.items()}


def ref_title(ref: dict[str, Any]) -> str | None:
    """Human title for a PR/issue/commit/comment/document/utterance projection."""
    kind = kind_of_id(ref.get("id"))
    title = ref.get("title")
    if kind == "pr":
        return f"PR #{ref.get('number')} {title or ''}".strip()
    if kind == "issue":
        return f"issue #{ref.get('number')} {title or ''}".strip()
    if kind == "commit":
        return f"commit {short_sha(ref.get('sha')) or ''} {title or ''}".strip()
    if kind == "comment":
        return f"{(ref.get('kind') or 'comment').replace('_', ' ')} by {ref.get('author') or 'unknown'}"
    if kind == "document":
        return f"{'ADR' if ref.get('kind') == 'adr' else 'document'} {title or ''}".strip()
    if kind == "utterance":
        return f"handover call, {ref.get('speaker') or ref.get('author') or 'speaker'}"
    if kind == "meeting":
        return f"handover call '{title}'" if title else "handover call"
    return title


def describe_where(ref: dict[str, Any] | None) -> str:
    """"PR #812 'Limit concurrency after SMTP errors'", "commit 3fa2c1d 'Bump retry'", "ADR 'Use Postgres'"."""
    if not ref:
        return "an unrecorded source"
    kind = kind_of_id(ref.get("id"))
    title = squash(ref.get("title"), 90)
    if kind == "pr":
        return f"PR #{ref.get('number')}" + (f" '{title}'" if title else "")
    if kind == "issue":
        return f"issue #{ref.get('number')}" + (f" '{title}'" if title else "")
    if kind == "commit":
        return f"commit {short_sha(ref.get('sha'))}" + (f" '{title}'" if title else "")
    if kind == "comment":
        return f"a {(ref.get('kind') or 'comment').replace('_', ' ')}"
    if kind == "document":
        return (f"ADR '{title}'" if ref.get("kind") == "adr" else f"the document '{title}'") if title else "a design document"
    if kind in ("utterance", "meeting"):
        return f"the handover call '{title}'" if title else "a handover call"
    return title or "an unrecorded source"


def when(ref: dict[str, Any] | None, fallback_ms: int | None = None) -> str | None:
    ms = (ref or {}).get("created_at") or (ref or {}).get("merged_at") or (ref or {}).get("authored_at") or fallback_ms
    return fmt_date(ms)


# ------------------------------------------------------------------------------------------------------------------
# Gathering


def gather(
    graph: Graph, repo: str, decision: RouterDecision, *, now_ms: int | None = None, recorder: Recorder | None = None
) -> Evidence:
    """Resolve entities, collect decisions (by entity, by reference, by text), fall back to PRs/commits, rank
    people, and fetch the neighbourhood subgraph."""
    rec = recorder or Recorder(graph)
    now_ms = now_ms or int(time.time() * 1000)
    decision = scrub_repo_terms(decision, repo)
    ev = Evidence(repo=repo, question=decision.question, decision=decision, calls=rec.calls)

    resolved = resolve_entities(rec, repo, decision) if decision.terms or decision.mentions else []
    ev.entities = [e for e in resolved if e.matched]
    ev.related = [e for e in resolved if not e.matched]
    entity_ids = [e.id for e in ev.entities]

    rankings: list[list[str]] = []
    versions: dict[str, Version] = {}

    def absorb(rows: list[dict[str, Any]], *, ranked_by: str | None = None) -> None:
        ranking: list[str] = []
        for row in rows:
            v = versions.get(row["id"])
            if v is None:
                v = version_from_row(row)
                versions[v.id] = v
            elif row.get("in_force") is not None:
                v.in_force = row["in_force"]
            if ranked_by is None or (row.get(ranked_by) or 0) > 0:
                ranking.append(row["id"])
        if ranking:
            rankings.append(ranking)

    if entity_ids:
        absorb(rec.run("decisions_about", {"repo": repo, "ids": entity_ids, "terms": decision.terms, "limit": 12, "chain_limit": 60}))
    if decision.numbers:
        ref_ids = [pr_id(repo, n) for n in decision.numbers] + [issue_id(repo, n) for n in decision.numbers]
        ref_ids += [commit_id(repo, m) for m in decision.mentions if _looks_like_sha(m)]
        absorb(rec.run("decisions_for_ref", {"repo": repo, "ids": ref_ids, "limit": 8, "chain_limit": 32}))
    if decision.lucene and decision.intent != "who_to_ask":
        absorb(rec.run("decision_search", {"repo": repo, "q": decision.lucene, "limit": 6, "chain_limit": 24}), ranked_by="hit_score")
    if decision.intent == "belief_at" and decision.at_ms is not None and entity_ids:
        absorb(rec.run("belief_at", {"repo": repo, "t": decision.at_ms, "ids": entity_ids, "limit": 24}))

    # A spoken (KT) statement points at the repository record it confirms or contradicts; fetch that record even
    # when the question's search did not reach it, so the answer can lead with the code and cite the call.
    partners = [(v.id, p["id"]) for v in versions.values() if v.kind == "kt" for p in v.confirms + v.contradicts if p.get("id")]
    for _kt_id, pid in partners[:4]:
        if pid in versions:
            continue
        root, chain, _ = why_path_rows(graph, pid, recorder=rec)
        for x in [root, *chain] if root is not None else []:
            versions.setdefault(x.id, x)

    # Fusion: a decision found by both entity and text ranks above one found by either alone; an exact entity
    # match lifts every decision about that entity.
    fused = rrf(rankings)
    strength = {e.id: e.strength for e in ev.entities}
    question_tokens = set(decision.terms)
    for v in versions.values():
        v.score = fused.get(v.id, 0.0)
        about_strength = max((strength.get(a.get("id"), 0.0) for a in v.about), default=0.0)
        v.score += 0.01 * about_strength
        # a file can carry hundreds of decisions: the ones whose subject the question actually names come first
        v.score += 0.02 * _subject_overlap(v, question_tokens)
    if decision.source == "kt":  # the question asks what was said on a call: spoken statements come first
        for v in versions.values():
            if v.kind == "kt":
                v.score += 0.05
    # a repository record fetched because a spoken statement points at it ranks with that statement, never above it
    for kt_id, pid in partners:
        if kt_id in versions and pid in versions:
            versions[pid].score = max(versions[pid].score, versions[kt_id].score)
    # Text-only hits must still be about something the question names, or share tokens with it, to count as anchored.
    if not entity_ids and not decision.numbers:
        versions = {vid: v for vid, v in versions.items() if _text_hit_is_anchored(v, decision)}
    # cap first, then demote: a moved setting's old chain stays in the evidence as history for the answer
    ev.dossiers = demote_moved(build_dossiers(versions)[:MAX_DOSSIERS], set(decision.mentions))

    if entity_ids and (not ev.dossiers or decision.intent in ("what_changed", "who_to_ask")):
        ev.prs = rec.run("prs_about_entity", {"ids": entity_ids, "limit": 6})
        ev.commits = rec.run("recent_commits_about", {"ids": entity_ids, "limit": 6})

    # Related-but-unmatched entities only lend their people when they share something specific with the question;
    # a generic match ("App" for "why does the app use Redis?") would name a stranger, so fall back to the repo.
    people_ids = entity_ids or [e.id for e in ev.related[:2] if e.strength > 0.2]
    if people_ids:
        ev.people = [person_from_row(r) for r in rec.run("person_to_ask", {"repo": repo, "ids": people_ids, "now": now_ms, "limit": 4}) if not _is_bot(r)]
    if not ev.people:  # nothing matched: the people who shaped the repository recently are still worth naming
        ev.people = [person_from_row(r, scope="this repository") for r in rec.run("repo_people", {"repo": repo, "now": now_ms, "limit": 4}) if not _is_bot(r)]
    ev.people = ev.people[:3]

    seeds: list[str] = []
    for d in ev.dossiers[:2]:
        for v in d.versions:
            seeds.extend(v.ref_ids)
    seeds.extend(entity_ids)
    seeds.extend(pr["id"] for pr in ev.prs[:3])
    seeds.extend(c["id"] for c in ev.commits[:3])
    seeds = list(dict.fromkeys(s for s in seeds if s))[:16]
    if seeds:
        rows = rec.run("neighbourhood", {"ids": seeds, "per_seed": 5, "limit": 60})
        if rows:
            ev.subgraph = {
                "nodes": [
                    {"id": n["id"], "label": n.get("label") or label_of(n.get("id")), "props": {k: v for k, v in (n.get("props") or {}).items() if v not in (None, "")}}
                    for n in rows[0].get("nodes") or []
                ],
                "edges": list(rows[0].get("edges") or []),
            }

    ev.route = f"{'entity' if entity_ids else 'ref' if decision.numbers else 'text'}_{decision.intent}"
    log.info(
        "gathered repo=%s intent=%s entities=%d dossiers=%d prs=%d commits=%d people=%d",
        repo, decision.intent, len(ev.entities), len(ev.dossiers), len(ev.prs), len(ev.commits), len(ev.people),
    )
    return ev


def _is_bot(row: dict[str, Any]) -> bool:
    login = (row.get("login") or row.get("id") or "").lower()
    return login.endswith("[bot]") or login.endswith("-bot") or login in ("dependabot", "renovate", "github-actions")


def _subject_tokens(v: Version) -> set[str]:
    raw = (v.subject or "") + " " + (v.key or "").split("|", 1)[0]
    for sep in ("|", "::", "/", ".", "_", "-", ":"):
        raw = raw.replace(sep, " ")
    return {t for t in raw.lower().split() if len(t) > 1 and t not in _GENERIC}


_GENERIC = frozenset({"toml", "yaml", "yml", "json", "go", "py", "ts", "js", "md", "sample", "config", "cfg", "env", "ini", "mod", "sum", "lock", "txt"})


def _subject_overlap(v: Version, question_tokens: set[str]) -> float:
    own = _subject_tokens(v)
    if not own or not question_tokens:
        return 0.0
    return len(own & question_tokens) / len(own)


def _looks_like_sha(text: str) -> bool:
    return 7 <= len(text) <= 40 and all(c in "0123456789abcdef" for c in text.lower())


def _text_hit_is_anchored(v: Version, decision: RouterDecision) -> bool:
    """A decision found only by full text counts when the question's terms cover most of its subject, the shared
    words are not all generic, and they are not merely a fragment of an identifier the question names (the `db` of
    "MongoDB" does not make `db.host` the answer)."""
    own = _subject_tokens(v)
    shared = own & set(decision.terms)
    if not own or not shared & set(specific_terms(decision)):
        return False
    coverage = len(shared) / len(own)
    for mention in decision.mentions:
        mention_tokens = set(tokens(mention).split())
        if mention_tokens and shared <= mention_tokens and len(shared) < len(mention_tokens):
            coverage *= len(shared) / len(mention_tokens)
            break
    return coverage >= 0.5


def why_path_rows(graph: Graph, decision_id: str, *, recorder: Recorder | None = None) -> tuple[Version | None, list[Version], Recorder]:
    """`32_why_path`: the decision and its chain (root first, then the others oldest to newest)."""
    rec = recorder or Recorder(graph)
    rows = rec.run("why_path", {"id": decision_id})
    root: Version | None = None
    others: list[Version] = []
    for row in rows:
        v = version_from_row(row)
        if row.get("is_root"):
            root = v
        else:
            others.append(v)
    others.sort(key=lambda v: (v.valid_from or 0, v.id))
    return root, others, rec


__all__ = [
    "Dossier", "Evidence", "PersonToAsk", "Recorder", "Version", "build_dossiers", "describe_where", "gather",
    "person_from_row", "ref_title", "rrf", "version_from_row", "when", "why_path_rows",
]
