"""Deterministic knowledge-risk scoring for Untangle Pulse.

The graph supplies facts; this module turns those facts into stable categories, scores,
ids, and human-readable reasons. No language model is involved in ranking a risk.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from untangle.answer.models import (
    EntityRef,
    PersonCard,
    PulseResponse,
    PulseRisk,
    PulseSummary,
    Ref,
)
from untangle.answer.text import iso

SIGNAL_WEIGHTS: dict[str, float] = {
    "contradiction": 0.72,
    "drift": 0.16,
    "ownership_gap": 0.14,
    "rationale_gap": 0.11,
    "stale": 0.08,
}
SIGNAL_LABELS = {
    "contradiction": "Handover call contradicts the active code decision",
    "drift": "Related code changed after this decision was recorded",
    "ownership_gap": "No recent owner is attached to this decision",
    "rationale_gap": "The active decision has no recorded rationale or evidence",
    "stale": "This decision is older than the radar freshness window",
}
CATEGORIES = ("contradiction", "drift", "ownership_gap", "rationale_gap", "stale")


def _truthy(signals: Mapping[str, Any], name: str) -> bool:
    value = signals.get(name)
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "y"}
    return bool(value)


def classify(signals: Mapping[str, Any]) -> str:
    """Return the most actionable category, with contradictions taking precedence."""
    for name in CATEGORIES:
        if _truthy(signals, name):
            return name
    return "rationale_gap"


def score(signals: Mapping[str, Any]) -> float:
    """Add signal weights and clamp to a two-decimal score in [0, 1]."""
    value = sum(weight for name, weight in SIGNAL_WEIGHTS.items() if _truthy(signals, name))
    return round(min(1.0, max(0.0, value)), 2)


def reasons(signals: Mapping[str, Any]) -> list[str]:
    return [SIGNAL_LABELS[name] for name in CATEGORIES if _truthy(signals, name)]


def risk_id(repo: str, decision_id: str, entity_id: str) -> str:
    """Generate a compact stable id without exposing an unbounded composite key."""
    raw = f"{repo}\x00{decision_id}\x00{entity_id}".encode()
    return f"risk:{hashlib.sha1(raw).hexdigest()[:16]}"


def _entity(row: Mapping[str, Any]) -> EntityRef:
    return EntityRef(
        id=str(row.get("id") or ""),
        label=str(row.get("label") or row.get("labels", ["Entity"])[0]),
        name=row.get("name"),
        path=row.get("path"),
        key=row.get("key"),
    )


def _person(row: Mapping[str, Any] | None) -> PersonCard | None:
    if not row or not row.get("id"):
        return None
    return PersonCard(id=str(row["id"]), name=row.get("name"), login=row.get("login"), score=row.get("score"))


def _ref(row: Mapping[str, Any]) -> Ref:
    return Ref(
        id=str(row.get("id") or ""), kind=str(row.get("kind") or row.get("label") or "entity"),
        title=row.get("title") or row.get("name"), url=row.get("url"), number=row.get("number"),
        created_at_iso=row.get("created_at_iso") or row.get("at_iso") or iso(row.get("created_at")), excerpt=row.get("excerpt"), author=row.get("author"),
    )


def build_risk(row: Mapping[str, Any], *, repo: str) -> PulseRisk | None:
    """Map one query row into a validated risk; rows without a scored signal are ignored."""
    signal_map = {name: _truthy(row, name) for name in CATEGORIES}
    risk_score = score(signal_map)
    if risk_score <= 0:
        return None
    entity_row = row.get("entity") or {}
    decision_row = row.get("decision") or {}
    entity_id = str(entity_row.get("id") or "")
    decision_id = str(decision_row.get("id") or "")
    if not entity_id or not decision_id:
        return None
    from untangle.answer.retrieve import version_from_row
    from untangle.answer.service import decision_card  # avoid importing service at module import time
    version = version_from_row(decision_row)
    return PulseRisk(
        id=risk_id(repo, decision_id, entity_id), category=classify(signal_map), score=risk_score,
        reasons=reasons(signal_map), entity=_entity(entity_row), decision=decision_card(version),
        owner=_person(row.get("owner")), evidence=[_ref(x) for x in (row.get("evidence") or []) if x.get("id")],
        contradictions=[_ref(x) for x in (row.get("contradictions") or []) if x.get("id")],
        last_touched_iso=row.get("last_touched_iso") or iso(row.get("last_touched")), owner_last_active_iso=row.get("owner_last_active_iso") or iso(row.get("owner_last_active")),
    )


def build_response(rows: Sequence[Mapping[str, Any]], *, repo: str, generated_at_iso: str, limit: int = 24) -> PulseResponse:
    risks = [risk for row in rows for risk in [build_risk(row, repo=repo)] if risk]
    risks.sort(key=lambda r: (-r.score, r.category, r.id))
    risks = risks[: max(1, min(limit, 50))]
    active = max((int(row.get("active_decisions") or 0) for row in rows), default=0)
    counts = {name: sum(1 for r in risks if r.category == name) for name in CATEGORIES}
    return PulseResponse(
        repo=repo, generated_at_iso=generated_at_iso, risks=risks,
        summary=PulseSummary(
            active_decisions=active, risks=len(risks), critical=sum(1 for r in risks if r.score >= 0.72),
            coverage=round((active - len(risks)) / active, 3) if active else 1.0,
            contradictions=counts["contradiction"], drift=counts["drift"], ownership_gaps=counts["ownership_gap"],
        ),
    )


__all__ = ["CATEGORIES", "SIGNAL_WEIGHTS", "build_response", "build_risk", "classify", "reasons", "risk_id", "score"]
