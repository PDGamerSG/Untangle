"""End to end on a real Neo4j: seed a small repo (Repo, Person, File, ConfigKey, PR, incident Issue, review Comment,
Commits, two Decisions in a SUPERSEDES chain through 21/22, Chunks with fake embeddings) and ask questions."""

from __future__ import annotations

import uuid

import pytest

from _answer_fixture import T_NOW, Fixture, seed_graph, unseed_people
from untangle.answer import service
from untangle.answer.retrieve import Recorder, gather
from untangle.answer.router import resolve_entities, route
from untangle.embed import FakeEmbedder
from untangle.llm import FakeLLM

pytestmark = pytest.mark.neo4j


@pytest.fixture(scope="module")
def seeded(graph):
    suffix = uuid.uuid4().hex[:6]
    repo = f"test/ans{suffix}"
    fx = seed_graph(graph, repo, suffix=suffix)
    yield fx
    unseed_people(graph, fx)
    graph.wipe_repo(repo)


def _ask(graph, fx: Fixture, question: str, **kw):
    return service.ask(question, fx.repo, graph=graph, llm=FakeLLM(), embedder=FakeEmbedder(384), now_ms=T_NOW, **kw)


def test_resolution_prefers_exact_matches(graph, seeded):
    rec = Recorder(graph)
    hits = resolve_entities(rec, seeded.repo, route("why is app.concurrency 10 in config.toml?"))
    assert [h.id for h in hits if h.matched][:2] == [seeded.cfg, seeded.file]
    assert all(h.strength == 1.0 for h in hits[:2])
    assert rec.calls[0].name == "30_resolve_entities" and rec.calls[0].rows >= 2


def test_why_returns_active_value_with_citations_and_supersession(graph, seeded):
    r = _ask(graph, seeded, "why is app.concurrency 10 in config.toml?")
    assert not r.refused
    assert r.answer.startswith(f"`app.concurrency` in `config.toml` is 10 [{seeded.dec_new}].")
    assert f"[{seeded.pr}]" in r.answer and f"[{seeded.issue}]" in r.answer and f"[{seeded.dec_old}]" in r.answer
    assert "The SMTP provider rate-limits above 10 concurrent connections" in r.answer
    assert "Person to ask: Kailash Nadh" in r.answer
    assert r.confidence.label == "high"
    assert "decision is active" in r.confidence.reasons and "linked to incident #790" in r.confidence.reasons
    assert [s.role for s in r.evidence_chain][:2] == ["decision", "discussion"]
    assert r.evidence_chain[0].id == seeded.dec_new and r.evidence_chain[0].status == "active"
    assert any(s.role == "incident" and s.id == seeded.issue for s in r.evidence_chain)
    assert any(s.role == "person" and s.name == "Kailash Nadh" for s in r.evidence_chain)
    assert r.evidence_chain[-1].role == "date" and r.evidence_chain[-1].iso == "2023-03-14T10:22:00Z"
    assert len(r.supersession) == 1
    assert r.supersession[0].newer == seeded.dec_new and r.supersession[0].older == seeded.dec_old
    assert r.supersession[0].signal == "config_diff"
    assert set(r.citations) >= {seeded.dec_new, seeded.pr, seeded.issue, seeded.dec_old}
    assert r.citations[seeded.pr].url.endswith("/pull/812")
    assert [e.id for e in r.entities][:2] == [seeded.cfg, seeded.file]
    names = [c.name for c in r.why.cypher]
    assert "30_resolve_entities" in names and "31_decisions_about" in names and "34_person_to_ask" in names and "37_neighbourhood" in names
    assert r.why.llm.used is False and r.why.route == "entity_why"
    assert any(n.label == "Decision" for n in r.why.subgraph.nodes)
    assert any(e.type == "SUPERSEDES" for e in r.why.subgraph.edges)
    assert len(r.why.subgraph.nodes) <= 60


def test_is_current_says_superseded(graph, seeded):
    r = _ask(graph, seeded, "do we still cap app.concurrency at 5?")
    assert r.intent == "is_current" and not r.refused
    assert r.answer.startswith(f"No — `app.concurrency` in `config.toml` was 5 until 14 Mar 2023 [{seeded.dec_old}].")
    assert "superseded on 14 Mar 2023 by 10" in r.answer
    yes = _ask(graph, seeded, "is app.concurrency still 10?")
    assert yes.answer.startswith("Yes —")


def test_belief_at_answers_as_of_date(graph, seeded):
    r = _ask(graph, seeded, "what was app.concurrency?", at="2022-05-01")
    assert r.intent == "belief_at" and r.at_iso == "2022-05-01T00:00:00Z"
    assert r.answer.startswith(f"On 1 May 2022 `app.concurrency` in `config.toml` was 5 [{seeded.dec_old}].")
    assert "later superseded on 14 Mar 2023 by 10" in r.answer
    assert r.evidence_chain[0].id == seeded.dec_old
    assert "decision was in force on 1 May 2022" in r.confidence.reasons


def test_who_to_ask_and_what_changed(graph, seeded):
    who = _ask(graph, seeded, "who should I ask about config.toml?")
    assert who.intent == "who_to_ask" and "Kailash Nadh" in who.answer and "authored 2 of 2 commits" in who.answer
    changed = _ask(graph, seeded, "what changed in app.concurrency?")
    assert changed.intent == "what_changed"
    assert "first 5 (commit 3fa2c1d" in changed.answer and "now 10 (PR #812" in changed.answer


def test_reference_question_finds_the_decision(graph, seeded):
    r = _ask(graph, seeded, "why was #812 merged?")
    assert not r.refused and f"[{seeded.dec_new}]" in r.answer
    assert any(c.name == "31_decisions_for_ref" and c.rows >= 1 for c in r.why.cypher)


def test_unanswerable_question_refuses_and_names_a_person(graph, seeded):
    r = _ask(graph, seeded, "why does the billing webhook retry twice?")
    assert r.refused and r.confidence.label == "refuse"
    assert r.answer.startswith("Untangle found nothing in the graph that answers that.")
    assert "Person to ask: Kailash Nadh" in r.answer
    assert r.evidence_chain == [] and r.citations == {} and r.why.route == "refuse"


def test_mode_both_returns_a_baseline(graph, seeded):
    r = _ask(graph, seeded, "why is app.concurrency 10 in config.toml?", mode="both")
    assert r.baseline is not None
    assert r.baseline.note == "vector-only, no graph: no supersession, no confidence"
    assert r.baseline.chunks and r.baseline.chunks[0].source_kind in ("pr", "issue", "commit")
    assert "[chunk:" in r.baseline.answer
    assert any(c.name == "50_vector_chunks" for c in r.why.cypher)
    only = _ask(graph, seeded, "why is app.concurrency 10 in config.toml?", mode="baseline")
    assert only.mode == "baseline" and only.baseline is not None and only.why.route == "baseline"


def test_gather_records_every_cypher_call(graph, seeded):
    rec = Recorder(graph)
    ev = gather(graph, seeded.repo, route("why is app.concurrency 10?"), now_ms=T_NOW, recorder=rec)
    assert ev.dossiers and [v.object for v in ev.dossiers[0].versions] == ["5", "10"]
    assert ev.people[0].counts == {"commit": 2, "decision": 2}
    assert all(c.ms is not None and c.rows >= 0 for c in rec.calls)


def test_why_path_entity_search_timeline_and_repos(graph, seeded):
    wp = service.why_path(seeded.dec_new, graph=graph)
    assert wp.decision.status == "active" and wp.decision.decided_in.number == 812
    assert [d.id for d in wp.older] == [seeded.dec_old] and wp.newer == []
    assert {e.id for e in wp.evidence} == {seeded.pr, seeded.comment}
    assert wp.motivated_by[0].id == seeded.issue and wp.implemented_by[0].id == seeded.commit_new
    assert wp.cypher[0].name == "32_why_path"
    with pytest.raises(service.NotFound):
        service.why_path("dec:nope", graph=graph)

    ent = service.entity(seeded.cfg, graph=graph, now_ms=T_NOW)
    assert ent.entity["key"] == "app.concurrency" and ent.entity["file"]["path"] == "config.toml"
    assert [d.id for d in ent.decisions] == [seeded.dec_new, seeded.dec_old]
    assert ent.people[0].name == "Kailash Nadh" and ent.recent_commits[0].sha.startswith("9b8c7d6e")

    found = service.search(seeded.repo, "concurrency", graph=graph)
    assert found.entities[0].id == seeded.cfg
    assert service.search(seeded.repo, "kailash", graph=graph).people[0].login == seeded.login

    tl = service.timeline(seeded.repo, "2022-05-01", graph=graph)
    assert [d.id for d in tl.active] == [seeded.dec_old] and [d.id for d in tl.superseded_since] == [seeded.dec_old]
    now = service.timeline(seeded.repo, None, graph=graph)
    assert [d.id for d in now.active] == [seeded.dec_new] and now.superseded_since == []

    repo = next(r for r in service.repos(graph=graph) if r.full_name == seeded.repo)
    assert repo.counts == {"commits": 2, "prs": 1, "issues": 1, "decisions": 2, "meetings": 0}
