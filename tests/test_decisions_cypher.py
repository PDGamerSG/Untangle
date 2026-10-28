"""The supersession statement is the heart of the product; these tests pin its behaviour on a real Neo4j."""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.neo4j


def _row(repo: str, i: int, obj: str, valid_from: int, key: str = "config.toml::app.concurrency|config_value") -> dict:
    return {
        "id": f"dec:{repo}:config_value:{i}", "repo": repo, "kind": "config_value", "key": key,
        "subject": "config.toml::app.concurrency", "predicate": "config_value", "object": obj,
        "text": f"app.concurrency is {obj}", "rationale": None, "valid_from": valid_from, "confidence": 0.95,
        "signal": "config_diff", "created_at": valid_from,
    }


def test_same_key_new_value_supersedes_and_keeps_history(graph, test_repo):
    now = int(time.time() * 1000)
    graph.run_named("record_decision", {"rows": [_row(test_repo, 1, "10", 1_000)], "now": now}, write=True)
    out = graph.run_named("record_decision", {"rows": [_row(test_repo, 2, "20", 2_000)], "now": now}, write=True).records
    assert out[0]["superseded"] == [f"dec:{test_repo}:config_value:1"]
    rows = graph.read(
        "MATCH (d:Decision {repo: $repo}) RETURN d.id AS id, d.status AS status, d.valid_to AS valid_to ORDER BY d.valid_from",
        {"repo": test_repo},
    ).records
    assert [r["status"] for r in rows] == ["superseded", "active"]
    assert rows[0]["valid_to"] == 2_000
    chain = graph.read(
        "MATCH (n:Decision)-[s:SUPERSEDES]->(o:Decision) WHERE n.repo = $repo RETURN n.id AS n, o.id AS o, s.signal AS signal",
        {"repo": test_repo},
    ).records
    assert chain == [{"n": f"dec:{test_repo}:config_value:2", "o": f"dec:{test_repo}:config_value:1", "signal": "config_diff"}]


def test_same_value_is_a_confirmation_not_a_supersession(graph, test_repo):
    now = int(time.time() * 1000)
    graph.run_named("record_decision", {"rows": [_row(test_repo, 1, "10", 1_000), _row(test_repo, 2, "10", 2_000)], "now": now}, write=True)
    statuses = graph.read("MATCH (d:Decision {repo: $repo}) RETURN collect(d.status) AS s", {"repo": test_repo}).scalar()
    assert sorted(statuses) == ["active", "active"]


def test_late_import_of_an_older_value_slots_into_the_chain(graph, test_repo):
    now = int(time.time() * 1000)
    graph.run_named("record_decision", {"rows": [_row(test_repo, 2, "20", 2_000)], "now": now}, write=True)
    out = graph.run_named("record_decision", {"rows": [_row(test_repo, 1, "10", 1_000)], "now": now}, write=True).records
    assert out[0]["status"] == "superseded"
    active = graph.read("MATCH (d:Decision {repo: $repo, status: 'active'}) RETURN d.object AS o", {"repo": test_repo}).scalar()
    assert active == "20"


def test_re_ingest_is_idempotent(graph, test_repo):
    now = int(time.time() * 1000)
    rows = [_row(test_repo, 1, "10", 1_000), _row(test_repo, 2, "20", 2_000)]
    for _ in range(2):
        graph.run_named("record_decision", {"rows": rows, "now": now}, write=True)
    n = graph.read("MATCH (d:Decision {repo: $repo}) RETURN count(d) AS n", {"repo": test_repo}).scalar()
    edges = graph.read("MATCH (:Decision {repo: $repo})-[s:SUPERSEDES]->() RETURN count(s) AS n", {"repo": test_repo}).scalar()
    assert (n, edges) == (2, 1)


def test_link_decision_skips_missing_targets_and_explicit_supersedes(graph, test_repo):
    now = int(time.time() * 1000)
    graph.run_named("record_decision", {"rows": [_row(test_repo, 1, "10", 1_000, key="a|k"), _row(test_repo, 2, "x", 2_000, key="b|k")], "now": now}, write=True)
    graph.query("CREATE (:Commit {id: $id, repo: $repo, sha: 'abc'})", {"id": f"commit:{test_repo}@abc", "repo": test_repo})
    linked = graph.run_named(
        "link_decision",
        {
            "rows": [
                {"decision_id": f"dec:{test_repo}:config_value:1", "rel": "IMPLEMENTED_BY", "target_id": f"commit:{test_repo}@abc", "props": {}},
                {"decision_id": f"dec:{test_repo}:config_value:1", "rel": "ABOUT", "target_id": "file:nope", "props": {}},
                {"decision_id": f"dec:{test_repo}:config_value:2", "rel": "SUPERSEDES", "target_id": f"dec:{test_repo}:config_value:1", "props": {"signal": "revert_commit"}},
            ],
            "now": now,
        },
        write=True,
    ).scalar()
    assert linked == 2
    old = graph.read("MATCH (d:Decision {id: $id}) RETURN d.status AS s, d.valid_to AS v", {"id": f"dec:{test_repo}:config_value:1"}).records[0]
    assert old == {"s": "superseded", "v": 2_000}


def test_re_recording_a_three_version_chain_changes_nothing(graph, test_repo):
    """Re-ingesting must not link an old version straight to the newest one or move its valid_to."""
    now = int(time.time() * 1000)
    rows = [_row(test_repo, 1, "100", 1_000), _row(test_repo, 2, "5", 2_000), _row(test_repo, 3, "10", 3_000)]
    for _ in range(2):
        for row in rows:  # one key per call, chronological rounds, as the loader records them
            graph.run_named("record_decision", {"rows": [row], "now": now}, write=True)
    chain = graph.read(
        "MATCH (a:Decision)-[s:SUPERSEDES]->(b:Decision) WHERE a.repo = $repo RETURN a.object AS n, b.object AS o, s.signal AS signal ORDER BY b.valid_from",
        {"repo": test_repo},
    ).records
    assert chain == [{"n": "5", "o": "100", "signal": "config_diff"}, {"n": "10", "o": "5", "signal": "config_diff"}]
    valid_to = graph.read("MATCH (d:Decision {repo: $repo}) WITH d ORDER BY d.valid_from RETURN d.object AS o, d.valid_to AS v", {"repo": test_repo}).records
    assert valid_to == [{"o": "100", "v": 2_000}, {"o": "5", "v": 3_000}, {"o": "10", "v": None}]


def test_late_import_slots_before_its_immediate_successor(graph, test_repo):
    now = int(time.time() * 1000)
    for row in (_row(test_repo, 2, "5", 2_000), _row(test_repo, 3, "10", 3_000)):
        graph.run_named("record_decision", {"rows": [row], "now": now}, write=True)
    graph.run_named("record_decision", {"rows": [_row(test_repo, 1, "100", 1_000)], "now": now}, write=True)
    linked = graph.read(
        "MATCH (n:Decision)-[s:SUPERSEDES]->(o:Decision {object: '100'}) WHERE n.repo = $repo RETURN n.object AS n, o.valid_to AS v",
        {"repo": test_repo},
    ).records
    assert linked == [{"n": "5", "v": 2_000}], "the old value is replaced by the next one in time, not by the newest"


def test_wipe_repo_removes_the_repo_node_too(graph, test_repo):
    graph.query("MERGE (r:Repo {id: $id}) SET r.full_name = $repo", {"id": f"repo:{test_repo}", "repo": test_repo})
    graph.wipe_repo(test_repo)
    assert graph.read("MATCH (r:Repo {full_name: $repo}) RETURN count(r) AS n", {"repo": test_repo}).scalar() == 0
