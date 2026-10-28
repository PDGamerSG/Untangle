"""Confidence from graph signals only (CONTRACTS §7): never from the model.

Signals: number of independent evidence nodes, source authority (ADR 1.0 > PR review 0.8 > PR body 0.7 > commit
message 0.6 > issue comment 0.5 > KT 0.5), whether the leading decision is active, agreement among decisions, entity
match strength, recency and whether an incident is linked. Thresholds: high >= 0.75, medium >= 0.5, low otherwise;
refuse below 0.2 or when nothing is anchored on a resolved entity. `score()` is a pure function of `Signals`;
`signals_from()` derives them from gathered evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from untangle.answer.models import Confidence
from untangle.answer.text import MS_PER_DAY, fmt_date, kind_of_id

if TYPE_CHECKING:
    from untangle.answer.retrieve import Evidence

HIGH, MEDIUM, REFUSE = 0.75, 0.5, 0.2

# source kind -> authority; `kind` for comments is the Comment.kind, for documents Document.kind
AUTHORITY: dict[str, float] = {
    "adr": 1.0, "design": 0.9, "document": 0.8, "pr_review": 0.8, "pr_review_comment": 0.8, "pr": 0.7, "pr_comment": 0.6,
    "commit": 0.6, "issue_comment": 0.5, "issue": 0.5, "utterance": 0.5, "meeting": 0.5, "kt": 0.5, "comment": 0.5,
}
AUTHORITY_LABEL: dict[str, str] = {
    "adr": "an ADR", "design": "a design document", "document": "a document", "pr_review": "a PR review",
    "pr_review_comment": "a PR review comment", "pr": "the PR discussion", "pr_comment": "a PR comment",
    "commit": "a commit message", "issue_comment": "an issue comment", "issue": "an issue", "utterance": "a handover call",
    "meeting": "a handover call", "kt": "a handover call", "comment": "a comment",
}

WEIGHTS = {"evidence": 0.25, "authority": 0.25, "active": 0.15, "agreement": 0.10, "match": 0.15, "recency": 0.05, "incident": 0.05}


@dataclass
class Signals:
    """Everything the score looks at. All derived from the graph."""

    anchored: bool = False  # some decision/PR/commit is attached to a resolved entity or reference
    has_decision: bool = False
    evidence_count: int = 0  # distinct evidence nodes behind the leading decision (or fallback PRs + commits)
    authorities: list[float] = field(default_factory=list)  # one per evidence node
    authority_kinds: list[str] = field(default_factory=list)
    top_active: bool = False  # leading decision active (or in force at the asked time)
    top_status: str | None = None
    agreement: float = 1.0  # 1.0 unless active decisions with the same key disagree
    match_strength: float = 0.0  # best resolved entity
    matched_name: str | None = None
    age_days: float | None = None  # age of the leading decision's valid_from
    has_incident: bool = False
    incident_label: str | None = None
    stated_by_known: bool = False
    spoken: str | None = None  # 'confirms' | 'contradicts' when a handover call speaks to the leading decision
    at_ms: int | None = None


def authority_of(ref: dict[str, Any]) -> tuple[float, str]:
    """(authority, kind) of an evidence/decided_in projection, by id prefix and node kind."""
    kind = kind_of_id(ref.get("id"))
    sub = (ref.get("kind") or "").lower()
    if kind == "document":
        key = sub if sub in AUTHORITY else "document"
    elif kind == "comment":
        key = sub if sub in AUTHORITY else "comment"
    else:
        key = kind
    return AUTHORITY.get(key, 0.4), key


def signals_from(evidence: Evidence, *, at_ms: int | None = None, now_ms: int | None = None) -> Signals:
    """Derive the signals from gathered evidence. The leading decision is the top dossier's active (or, for
    `belief_at`, in-force) version."""
    import time

    now_ms = now_ms or int(time.time() * 1000)
    s = Signals(anchored=evidence.anchored, at_ms=at_ms)
    if evidence.entities:
        best = max(evidence.entities, key=lambda e: e.strength)
        s.match_strength, s.matched_name = best.strength, best.display
    led = evidence.lead(at_ms)
    if led is not None:
        s.has_decision = True
        lead = led[1]
        s.top_status = lead.status
        s.top_active = lead.in_force_at(at_ms) if at_ms is not None else lead.active
        seen: set[str] = set()
        for ref in [lead.decided_in, *lead.evidence, *lead.implemented_by, *lead.motivated_by]:
            if not ref or not ref.get("id") or ref["id"] in seen:
                continue
            seen.add(ref["id"])
            a, k = authority_of(ref)
            s.authorities.append(a)
            s.authority_kinds.append(k)
        spoken = evidence.spoken(lead)
        if spoken:
            s.spoken = spoken[0]
            if spoken[1].get("id") and spoken[1]["id"] not in seen:
                seen.add(spoken[1]["id"])
                s.authorities.append(AUTHORITY["kt"])
                s.authority_kinds.append("kt")
        s.evidence_count = len(seen)
        if lead.valid_from:
            s.age_days = max(0.0, (now_ms - lead.valid_from) / MS_PER_DAY)
        incidents = lead.incidents
        if incidents:
            s.has_incident = True
            s.incident_label = f"#{incidents[0].get('number')}" if incidents[0].get("number") else incidents[0].get("title")
        s.stated_by_known = bool(lead.stated_by and lead.stated_by.get("name"))
        # agreement: active decisions sharing a key but not an object disagree
        active_by_key: dict[str, set[str]] = {}
        for v in evidence.versions:
            if v.active and v.key:
                active_by_key.setdefault(v.key, set()).add(v.object or "")
        conflicts = sum(1 for objs in active_by_key.values() if len(objs) > 1)
        s.agreement = 1.0 if not conflicts else max(0.0, 1.0 - 0.5 * conflicts)
        if s.spoken == "contradicts":
            s.agreement = min(s.agreement, 0.0)
        if not s.match_strength and lead.about:
            s.match_strength = 0.5  # found by text or reference, not by a named entity
    elif evidence.prs or evidence.commits:
        s.evidence_count = len(evidence.prs) + len(evidence.commits)
        s.authorities = [AUTHORITY["pr"]] * len(evidence.prs) + [AUTHORITY["commit"]] * len(evidence.commits)
        s.authority_kinds = ["pr"] * len(evidence.prs) + ["commit"] * len(evidence.commits)
        newest = max([p.get("merged_at") or p.get("created_at") or 0 for p in evidence.prs] + [c.get("authored_at") or 0 for c in evidence.commits], default=0)
        if newest:
            s.age_days = max(0.0, (now_ms - newest) / MS_PER_DAY)
        s.has_incident = any(i.get("is_incident") for p in evidence.prs for i in (p.get("closes") or []))
    return s


def score(s: Signals) -> Confidence:
    """Weighted sum in [0, 1] with short, human reasons used verbatim by the UI."""
    reasons: list[str] = []
    if not s.anchored:
        return Confidence(score=0.0, label="refuse", reasons=["no decision or evidence is anchored on an entity the question names"])

    n = s.evidence_count
    evidence_part = WEIGHTS["evidence"] * min(n, 4) / 4.0
    if n == 0:
        reasons.append("no supporting evidence node beyond the decision itself")
    else:
        reasons.append(f"{n} independent source{'s' if n != 1 else ''}")

    best_authority = max(s.authorities, default=0.0)
    authority_part = WEIGHTS["authority"] * best_authority
    if s.authorities:
        best_kind = s.authority_kinds[s.authorities.index(best_authority)]
        reasons.append(f"backed by {AUTHORITY_LABEL.get(best_kind, 'a source')}")

    if s.has_decision:
        if s.top_active:
            active_part = WEIGHTS["active"]
            reasons.append(f"decision was in force on {fmt_date(s.at_ms)}" if s.at_ms is not None else "decision is active")
        else:
            active_part = WEIGHTS["active"] * 0.4
            reasons.append("the leading decision was superseded" if s.top_status == "superseded" else "the leading decision is not active")
    else:
        active_part = 0.0
        reasons.append("no recorded decision; built from pull requests and commits only")

    agreement_part = WEIGHTS["agreement"] * s.agreement
    if s.spoken == "contradicts":
        reasons.append("a recorded handover call contradicts the repository record")
    elif s.agreement < 1.0:
        reasons.append("active decisions disagree on the same key")
    if s.spoken == "confirms":
        reasons.append("a recorded handover call confirms it")

    match_part = WEIGHTS["match"] * s.match_strength
    if s.match_strength >= 1.0:
        reasons.append(f"entity matched exactly ({s.matched_name})" if s.matched_name else "entity matched exactly")
    elif s.match_strength > 0:
        reasons.append(f"entity match is partial ({int(round(s.match_strength * 100))}%)" + (f": {s.matched_name}" if s.matched_name else ""))
    else:
        reasons.append("no entity in the question matched the graph")

    recency_part = 0.0
    if s.age_days is not None:
        recency_part = WEIGHTS["recency"] * max(0.0, 1.0 - s.age_days / 3650.0)
        years = s.age_days / 365.0
        if years < 1:
            reasons.append("decided within the last year")
        elif years >= 2:
            reasons.append(f"the decision is {int(years)} years old")

    incident_part = WEIGHTS["incident"] if s.has_incident else 0.0
    if s.has_incident:
        reasons.append(f"linked to incident {s.incident_label}" if s.incident_label else "linked to an incident")

    if s.has_decision and s.stated_by_known:
        reasons.append("stated by a named person")

    total = evidence_part + authority_part + active_part + agreement_part + match_part + recency_part + incident_part
    if not s.has_decision:
        total = min(total, MEDIUM - 0.01)
    total = round(max(0.0, min(1.0, total)), 2)
    if total < REFUSE:
        return Confidence(score=total, label="refuse", reasons=reasons + ["confidence below the refusal threshold"])
    label = "high" if total >= HIGH else "medium" if total >= MEDIUM else "low"
    return Confidence(score=total, label=label, reasons=reasons)


__all__ = ["AUTHORITY", "HIGH", "MEDIUM", "REFUSE", "WEIGHTS", "Signals", "authority_of", "score", "signals_from"]
