"""Eval harness against a fake `ask`: gold loading, metric computation, duck-typed responses, report writing."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from kyun.eval.gold import load_gold
from kyun.eval.harness import call_ask, normalise_response, percentile, run_eval

GOLD = Path(__file__).resolve().parents[1] / "eval" / "gold" / "listmonk.yaml"


def test_listmonk_gold_set_has_25_questions_in_the_agreed_buckets():
    gold = load_gold(GOLD)
    assert gold.repo == "knadh/listmonk" and gold.name == "listmonk"
    assert len(gold.questions) == 25
    by_intent: dict[str, int] = {}
    for q in gold.questions:
        by_intent[q.intent] = by_intent.get(q.intent, 0) + 1
    assert by_intent["refuse"] == 5 and all(q.expect.refuse for q in gold.questions if q.intent == "refuse")
    assert by_intent["who_to_ask"] == 6  # five about the repo, one about the KT call
    assert sum(1 for q in gold.questions if q.id.startswith("kt-")) == 5
    assert sum(1 for q in gold.questions if q.intent in ("config_value", "entity_why", "dependency", "supersession")) == 10
    assert 0 < len(gold.unverified) < len(gold.questions)
    assert all(q.expect.person_any for q in gold.questions if q.intent == "who_to_ask")
    assert all(q.expect.answer_contains_any or q.expect.cites_any for q in gold.questions if q.intent in ("config_value", "kt"))


def _fake_ask(question: str, repo: str, *, mode: str = "graph", at: str | None = None):
    """Graph mode answers correctly; baseline never cites, never refuses and never shows supersession."""
    assert repo == "test/repo"
    if mode == "baseline":
        return {"question": question, "repo": repo, "mode": mode, "answer": "retry limit is 3 and then 5", "refused": False, "citations": {}, "evidence_chain": [], "entities": [], "supersession": [], "baseline": {"answer": "retry limit is 3 and then 5", "chunks": []}}
    if "MongoDB" in question or "Kafka" in question:
        return {"question": question, "repo": repo, "mode": mode, "answer": "Kyun found nothing in the graph that answers that.", "refused": True, "citations": {}, "evidence_chain": [], "entities": [], "supersession": []}
    if "who" in question.lower():
        return SimpleNamespace(
            answer="Ask Rahul: he authored most changes to cmd/retry.go [person:gh:rahul].", refused=False, citations={}, supersession=[],
            evidence_chain=[SimpleNamespace(role="person", id="person:gh:rahul", name="Rahul")], entities=[SimpleNamespace(id="file:test/repo:cmd/retry.go", name="retry.go", path="cmd/retry.go")],
            confidence=SimpleNamespace(score=0.7, label="medium"),
        )
    if "still" in question:
        return {"answer": "First retry_limit was 3 [dec:test/repo:config_value:old], now it is 5 [dec:test/repo:config_value:new].", "refused": False, "citations": {"dec:test/repo:config_value:new": {"kind": "decision"}}, "evidence_chain": [], "entities": [{"id": "cfg:test/repo:app.yaml::retry_limit", "key": "retry_limit"}], "supersession": [{"newer": "dec:test/repo:config_value:new", "older": "dec:test/repo:config_value:old"}], "confidence": {"score": 0.9}}
    if "explode" in question:
        raise RuntimeError("service exploded")
    return {"answer": "retry_limit is 3 because of incident #790 [dec:test/repo:config_value:abc]", "refused": False, "citations": {"dec:test/repo:config_value:abc": {"kind": "decision"}, "issue:test/repo#790": {}}, "evidence_chain": [{"role": "decision", "id": "dec:test/repo:config_value:abc"}], "entities": [{"id": "cfg:test/repo:app.yaml::retry_limit", "key": "retry_limit"}], "supersession": [], "confidence": {"score": 0.82}}


def _write_gold(tmp_path: Path) -> Path:
    gold = {
        "repo": "test/repo",
        "questions": [
            {"id": "q-value", "question": "Why is retry_limit 3?", "intent": "config_value", "expect": {"entities_any": ["retry_limit"], "answer_contains_any": ["3"], "cites_any": ["dec:test/repo:config_value"]}},
            {"id": "q-super", "question": "Do we still retry 3 times?", "intent": "supersession", "expect": {"answer_contains_any": ["5"], "superseded": True}},
            {"id": "q-mongo", "question": "Why MongoDB?", "intent": "refuse", "expect": {"refuse": True}},
            {"id": "q-kafka", "question": "Why was Kafka removed?", "intent": "refuse", "expect": {"refuse": True}},
            {"id": "q-who", "question": "Who should I ask about cmd/retry.go?", "intent": "who_to_ask", "expect": {"person_any": ["rahul"], "entities_any": ["cmd/retry.go"]}},
            {"id": "q-unv", "question": "Why is retry_limit 3 (unverified)?", "intent": "config_value", "unverified": True, "expect": {"answer_contains_any": ["3"], "cites_any": ["pr:test/repo#"]}},
            {"id": "q-err", "question": "please explode", "intent": "entity_why", "expect": {"answer_contains_any": ["x"]}},
        ],
    }
    path = tmp_path / "gold.yaml"
    path.write_text(yaml.safe_dump(gold, sort_keys=False), encoding="utf-8")
    return path


def test_run_eval_scores_graph_against_baseline_and_writes_the_report(tmp_path):
    out = tmp_path / "out" / "report.md"
    report = run_eval(_write_gold(tmp_path), ask=_fake_ask, out=out)
    assert report["questions"] == 7 and report["verified"] == 6 and report["unverified"] == 1 and report["modes"] == ["graph", "baseline"]
    g, b = report["summary"]["graph"]["verified"], report["summary"]["baseline"]["verified"]
    assert g["n"] == 6 and g["errors"] == 1
    # evidence applies to q-value and q-super (both have contains/cites) and q-err (errored => miss)
    assert g["evidence_accuracy"] == {"hits": 2, "n": 2, "rate": 1.0}
    # baseline: q-value misses (no citation), q-super hits (contains-only expectation), q-err misses (no error in this mode)
    assert b["evidence_accuracy"] == {"hits": 1, "n": 3, "rate": pytest.approx(1 / 3)} and b["errors"] == 0
    assert g["supersession_correctness"] == {"hits": 1, "n": 1, "rate": 1.0}
    assert b["supersession_correctness"] == {"hits": 0, "n": 1, "rate": 0.0}
    assert g["refusal"]["tp"] == 2 and g["refusal"]["fp"] == 0 and g["refusal"]["fn"] == 0 and g["refusal"]["precision"] == 1.0 and g["refusal"]["recall"] == 1.0
    assert b["refusal"]["recall"] == 0.0 and b["refusal"]["precision"] is None and b["refusal"]["f1"] is None
    assert g["person_hit_rate"] == {"hits": 1, "n": 1, "rate": 1.0} and g["entity_hit_rate"]["hits"] == 2
    assert g["latency_ms"]["p50"] is not None and g["latency_ms"]["p95"] >= g["latency_ms"]["p50"]
    unv = report["summary"]["graph"]["unverified"]
    assert unv["n"] == 1 and unv["evidence_accuracy"] == {"hits": 0, "n": 1, "rate": 0.0}  # cites pr:... which the fake never does
    runs = {(r["id"], r["mode"]): r for r in report["runs"]}
    assert runs[("q-err", "graph")]["error"].startswith("RuntimeError") and runs[("q-err", "graph")]["checks"]["evidence"] is None
    assert runs[("q-who", "graph")]["people"] == ["Rahul", "person:gh:rahul"] and runs[("q-who", "graph")]["confidence"] == 0.7
    assert runs[("q-super", "graph")]["citations"][:2] == ["dec:test/repo:config_value:new", "dec:test/repo:config_value:old"]
    assert runs[("q-mongo", "baseline")]["checks"]["refusal_correct"] is False
    assert Path(report["out"]) == out and out.is_file() and out.with_suffix(".json").is_file()
    md = out.read_text(encoding="utf-8")
    assert "## Summary (verified questions)" in md and "| Metric | graph | baseline |" in md
    assert "| Evidence-chain accuracy (cites + contains) | 2/2 (100%) | 1/3 (33%) |" in md
    assert "## Unverified expectations" in md and "q-unv *(unverified)*" in md
    assert "## Errors" in md and "service exploded" in md
    assert "| q-mongo | refuse | baseline | answered (wrong) |" in md


def test_modes_can_be_restricted_and_repo_overridden(tmp_path):
    seen = []

    def ask(question, repo, **kw):
        seen.append((repo, kw.get("mode"), kw.get("at")))
        return {"answer": "", "refused": True}

    gold = tmp_path / "g.yaml"
    gold.write_text(yaml.safe_dump({"repo": "x/y", "questions": [{"id": "a", "question": "q", "at": "2024-01-01", "expect": {"refuse": True}}]}), encoding="utf-8")
    report = run_eval(gold, ask=ask, modes=("graph",), out=tmp_path / "r.md", repo="z/w")
    assert seen == [("z/w", "graph", "2024-01-01")] and report["modes"] == ["graph"]
    assert report["summary"]["graph"]["verified"]["refusal"]["recall"] == 1.0


def test_call_ask_adapts_to_the_service_signature():
    assert call_ask(lambda q, r: (q, r), "q", "r", "baseline", None) == ("q", "r")
    assert call_ask(lambda q, r, mode="graph": (q, r, mode), "q", "r", "baseline", "2024") == ("q", "r", "baseline")
    assert call_ask(lambda q, r, **kw: kw, "q", "r", "graph", "2024") == {"mode": "graph", "at": "2024"}


def test_normalise_response_collects_citations_people_and_entities_from_dicts_and_objects():
    resp = SimpleNamespace(
        answer="x [dec:a:b:1] y [commit:a@abc]", refused=False, citations={"dec:a:b:1": {}}, entities=[SimpleNamespace(id="cfg:a:f::k", key="k", name=None, path=None)],
        evidence_chain=[SimpleNamespace(role="person", id="person:gh:x", name="X"), SimpleNamespace(role="discussion", id="pr:a#1")], supersession=None, confidence=0.5, baseline=None,
    )
    n = normalise_response(resp, "graph")
    assert n["citations"] == ["dec:a:b:1", "person:gh:x", "pr:a#1", "commit:a@abc"]
    assert n["people"] == ["X", "person:gh:x"] and n["entities"] == ["cfg:a:f::k", "k"] and n["confidence"] == 0.5 and n["supersession"] == []
    base = normalise_response({"answer": None, "refused": False, "baseline": {"answer": "from vectors"}}, "baseline")
    assert base["answer"] == "from vectors" and base["citations"] == []
    assert normalise_response(None, "graph")["refused"] is None


def test_percentile_is_nearest_rank():
    assert percentile([], 50) is None
    assert percentile([5.0], 95) == 5.0
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5 and percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10


def test_gold_validation_rejects_duplicate_ids_and_unknown_keys(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"repo": "x/y", "questions": [{"id": "a", "question": "q"}, {"id": "a", "question": "q2"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_gold(bad)
    bad.write_text(yaml.safe_dump({"repo": "x/y", "questions": [{"id": "a", "question": "q", "expect": {"nope": 1}}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_gold(bad)


def test_eval_cli_registers_and_runs(tmp_path, monkeypatch, capsys):
    from kyun.eval import cli

    gold = _write_gold(tmp_path)
    captured = {}

    def fake_run_eval(gold_path, *, modes, out, repo):
        captured.update(gold=str(gold_path), modes=modes, out=str(out), repo=repo)
        return {"out": str(out), "questions": 7, "summary": {m: {"verified": {"evidence_accuracy": {"hits": 1, "n": 2}, "supersession_correctness": {"hits": 0, "n": 0}, "person_hit_rate": {"hits": 0, "n": 0}, "refusal": {"precision": None, "recall": 1.0}, "latency_ms": {"p50": 12.0}, "errors": 0}} for m in modes}}

    monkeypatch.setattr(cli, "run_eval", fake_run_eval)
    parser = argparse.ArgumentParser()
    cli.register(parser.add_subparsers(dest="command"))
    args = parser.parse_args(["eval", "--repo", "knadh/listmonk", "--gold", str(gold), "--out", str(tmp_path / "r.md"), "--modes", "graph"])
    assert args.func(args) == 0
    assert captured == {"gold": str(gold), "modes": ("graph",), "out": str(tmp_path / "r.md"), "repo": "knadh/listmonk"}
    text = capsys.readouterr().out
    assert "wrote" in text and "evidence 1/2" in text and "refusal P/R n/a/1.00" in text
    with pytest.raises(SystemExit):
        parser.parse_args(["eval", "--repo", "r"])
