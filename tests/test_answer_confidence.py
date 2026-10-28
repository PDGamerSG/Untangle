"""Confidence: a pure function of graph signals with the CONTRACTS §7 thresholds."""

from __future__ import annotations

from _answer_fixture import T_NOW, Fixture
from untangle.answer.confidence import HIGH, MEDIUM, REFUSE, Signals, authority_of, score, signals_from


def test_nothing_anchored_refuses():
    c = score(Signals(anchored=False))
    assert c.label == "refuse" and c.score == 0.0
    assert "anchored" in c.reasons[0]


def test_rich_active_decision_is_high():
    c = score(Signals(anchored=True, has_decision=True, evidence_count=4, authorities=[0.8, 0.7, 0.6], authority_kinds=["pr_review", "pr", "commit"],
                      top_active=True, agreement=1.0, match_strength=1.0, matched_name="app.concurrency", age_days=300, has_incident=True, incident_label="#790", stated_by_known=True))
    assert c.label == "high" and c.score >= HIGH
    assert "4 independent sources" in c.reasons
    assert "backed by a PR review" in c.reasons
    assert "decision is active" in c.reasons
    assert "entity matched exactly (app.concurrency)" in c.reasons
    assert "linked to incident #790" in c.reasons
    assert "decided within the last year" in c.reasons
    assert "stated by a named person" in c.reasons


def test_superseded_top_scores_below_active():
    base = dict(anchored=True, has_decision=True, evidence_count=2, authorities=[0.7], authority_kinds=["pr"], match_strength=1.0, age_days=100)
    active = score(Signals(top_active=True, **base))
    superseded = score(Signals(top_active=False, top_status="superseded", **base))
    assert superseded.score < active.score
    assert "the leading decision was superseded" in superseded.reasons


def test_belief_at_reason_names_the_date():
    c = score(Signals(anchored=True, has_decision=True, evidence_count=1, authorities=[0.6], authority_kinds=["commit"], top_active=True, match_strength=1.0, at_ms=1651363200000))
    assert "decision was in force on 1 May 2022" in c.reasons


def test_no_decision_is_capped_below_medium():
    c = score(Signals(anchored=True, has_decision=False, evidence_count=6, authorities=[0.7] * 6, authority_kinds=["pr"] * 6, match_strength=1.0, age_days=10, has_incident=True))
    assert c.label == "low" and c.score < MEDIUM
    assert "no recorded decision; built from pull requests and commits only" in c.reasons


def test_weak_signals_refuse_below_threshold():
    c = score(Signals(anchored=True, has_decision=True, evidence_count=0, authorities=[], top_active=False, top_status="superseded", agreement=1.0, match_strength=0.0))
    assert c.score < REFUSE and c.label == "refuse"
    assert "no supporting evidence node beyond the decision itself" in c.reasons
    assert "confidence below the refusal threshold" in c.reasons


def test_disagreement_and_partial_match_are_reported():
    c = score(Signals(anchored=True, has_decision=True, evidence_count=2, authorities=[0.5], authority_kinds=["issue"], top_active=True, agreement=0.5, match_strength=0.5, matched_name="sender.go", age_days=1000))
    assert "active decisions disagree on the same key" in c.reasons
    assert "entity match is partial (50%): sender.go" in c.reasons
    assert "the decision is 2 years old" in c.reasons


def test_authority_table():
    assert authority_of({"id": "doc:r:adr/0007.md", "kind": "adr"}) == (1.0, "adr")
    assert authority_of({"id": "comment:r:pr_review:1", "kind": "pr_review"}) == (0.8, "pr_review")
    assert authority_of({"id": "pr:r#1"}) == (0.7, "pr")
    assert authority_of({"id": "commit:r@abc"}) == (0.6, "commit")
    assert authority_of({"id": "comment:r:issue_comment:1", "kind": "issue_comment"}) == (0.5, "issue_comment")
    assert authority_of({"id": "utt:r:m#0001"}) == (0.5, "utterance")


def test_signals_from_fixture_evidence():
    fx = Fixture("test/fixture")
    s = signals_from(fx.evidence(), now_ms=T_NOW)
    assert s.anchored and s.has_decision and s.top_active
    assert s.evidence_count == 4  # pr, comment, commit (implemented_by), issue
    assert max(s.authorities) == 0.8
    assert s.has_incident and s.incident_label == "#790"
    assert s.match_strength == 1.0 and s.matched_name == "app.concurrency in config.toml"
    assert s.stated_by_known
    c = score(s)
    assert c.label == "high"


def test_signals_from_belief_at_uses_the_version_in_force():
    fx = Fixture("test/fixture")
    at = 1651363200000  # 2022-05-01: the old value (5) was in force
    s = signals_from(fx.evidence("what was app.concurrency on 2022-05-01?", at="2022-05-01"), at_ms=at, now_ms=T_NOW)
    assert s.top_active and s.top_status == "superseded"
    assert s.evidence_count == 1


def test_signals_from_fallback_prs():
    fx = Fixture("test/fixture")
    ev = fx.evidence(with_dossiers=False)
    ev.prs = [{"id": fx.pr, "number": 812, "merged_at": 1678789320000, "closes": [{"id": fx.issue, "is_incident": True}]}]
    ev.commits = [{"id": fx.commit_new, "authored_at": 1678789320000}]
    s = signals_from(ev, now_ms=T_NOW)
    assert s.anchored and not s.has_decision and s.evidence_count == 2 and s.has_incident
    assert score(s).label == "low"
