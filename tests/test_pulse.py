from __future__ import annotations

from kyun.pulse import build_response, classify, risk_id, score


def test_contradiction_is_the_primary_signal_and_scores_highest():
    signals = {"contradiction": True, "drift": True, "ownership_gap": False, "rationale_gap": False, "stale": False}
    assert classify(signals) == "contradiction"
    assert score(signals) == 0.88


def test_scores_are_additive_but_clamped_and_categories_are_stable():
    signals = {"contradiction": True, "drift": True, "ownership_gap": True, "rationale_gap": True, "stale": True}
    assert score(signals) == 1.0
    assert classify({"ownership_gap": True}) == "ownership_gap"
    assert classify({"rationale_gap": True}) == "rationale_gap"
    assert risk_id("o/r", "dec:1", "file:1") == risk_id("o/r", "dec:1", "file:1")
    assert risk_id("o/r", "dec:1", "file:1") != risk_id("o/r", "dec:2", "file:1")


def test_build_response_summarises_risks_and_coverage():
    rows = [
        {
            "active_decisions": 10, "contradiction": True, "drift": False, "ownership_gap": False, "rationale_gap": False, "stale": False,
            "entity": {"id": "cfg:1", "label": "ConfigKey", "name": "app.limit", "path": "config.toml", "key": "app.limit"},
            "decision": {"id": "dec:1", "kind": "config_value", "key": "config.toml::app.limit|config_value", "subject": "config.toml::app.limit", "predicate": "config_value", "object": "3", "text": "limit is 3", "status": "active", "valid_from": 1000, "about": []},
            "owner": {"id": "person:1", "name": "Asha"}, "evidence": [{"id": "pr:1", "kind": "PullRequest", "title": "Set limit"}],
            "contradictions": [{"id": "dec:kt", "kind": "Decision", "title": "Call says 4"}], "last_touched_iso": "2026-01-01T00:00:00Z",
        },
    ]
    out = build_response(rows, repo="o/r", generated_at_iso="2026-01-02T00:00:00Z")
    assert out.summary.active_decisions == 10 and out.summary.risks == 1
    assert out.summary.contradictions == 1 and out.summary.coverage == 0.9
    assert out.risks[0].decision.object == "3" and out.risks[0].owner.name == "Asha"


def test_service_pulse_maps_query_rows(monkeypatch):
    from kyun.answer import service

    class FakeRecorder:
        def __init__(self, graph):
            self.graph = graph

        def run(self, name, params):
            assert name == "pulse" and params["limit"] == 24
            return [{
                "active_decisions": 2, "contradiction": False, "drift": True, "ownership_gap": False, "rationale_gap": False, "stale": False,
                "entity": {"id": "file:1", "label": "File", "name": "worker.go", "path": "worker.go"},
                "decision_id": "dec:2", "decision_kind": "change", "decision_key": "worker.go|change", "decision_subject": "worker.go",
                "decision_predicate": "changed", "decision_object": "retry path", "decision_text": "worker.go changed", "decision_rationale": None,
                "decision_status": "active", "decision_valid_from": 1000, "decision_valid_to": None, "decision_created_at": 1000,
                "decision_confidence": 0.8, "decision_signal": "pr_merge", "about": [], "stated_by": None, "decided_in": None,
                "motivated_by": [], "implemented_by": [], "evidence": [], "contradictions": [], "last_touched": 2000, "owner_last_active": 2000,
            }]

    monkeypatch.setattr(service, "Recorder", FakeRecorder)
    result = service.pulse("o/r", graph=object(), now_ms=2_000, limit=24)
    assert result.repo == "o/r" and result.risks[0].category == "drift"
    assert result.risks[0].last_touched_iso is not None
