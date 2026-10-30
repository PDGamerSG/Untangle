"""`cypher/60_pulse.cypher` on a real Neo4j: an owner's latest activity is right, and a prolific owner does not
multiply the query (the previous form expanded every commit times every review for each decision and timed out on
knadh/listmonk)."""

from __future__ import annotations

import time
import uuid

import pytest

pytestmark = pytest.mark.neo4j

DAY = 86_400_000


def _params(repo: str, now: int) -> dict:
    return {"repo": repo, "now": now, "stale_before": now - 365 * DAY, "owner_stale_before": now - 540 * DAY, "limit": 50}


def _seed(graph, repo: str, *, owner_id: str, decisions: int, commits: int, reviews: int, now: int) -> None:
    graph.query("MERGE (p:Person {id: $id}) SET p.name = 'Prolific Maintainer', p.login = 'prolific'", {"id": owner_id})
    graph.query(
        "UNWIND range(1, $n) AS i "
        "MATCH (p:Person {id: $owner}) "
        "CREATE (c:Commit {id: $repo + '@c' + i, repo: $repo, sha: 'c' + i, title: 'commit ' + i, authored_at: $start + i * 1000}) "
        "CREATE (p)-[:AUTHORED]->(c)",
        {"n": commits, "owner": owner_id, "repo": repo, "start": now - 900 * DAY},
    )
    graph.query(
        "UNWIND range(1, $n) AS i "
        "MATCH (p:Person {id: $owner}) "
        "CREATE (pr:PullRequest {id: $repo + '#' + i, repo: $repo, number: i, title: 'pr ' + i, "
        "  created_at: $start + i * 1000, merged_at: $start + i * 1000 + 500}) "
        "CREATE (p)-[:REVIEWED]->(pr)",
        {"n": reviews, "owner": owner_id, "repo": repo, "start": now - 800 * DAY},
    )
    graph.query(
        "UNWIND range(1, $n) AS i "
        "MATCH (p:Person {id: $owner}) "
        "CREATE (k:ConfigKey {id: 'cfg:' + $repo + ':app.key' + i, repo: $repo, name: 'key' + i, key: 'app.key' + i, path: 'config.toml'}) "
        "CREATE (d:Decision {id: 'dec:' + $repo + ':config_value:' + i, repo: $repo, kind: 'config_value', status: 'active', "
        "  key: 'config.toml::app.key' + i + '|config_value', subject: 'config.toml::app.key' + i, predicate: 'config_value', "
        "  object: toString(i), text: 'app.key' + i + ' is ' + i, valid_from: $start + i, confidence: 0.9, signal: 'config_diff', "
        "  created_at: $start + i}) "
        "CREATE (d)-[:ABOUT]->(k) "
        "CREATE (d)-[:STATED_BY]->(p)",
        {"n": decisions, "owner": owner_id, "repo": repo, "start": now - 1000 * DAY},
    )


def test_prolific_owner_does_not_blow_up_pulse(graph, test_repo):
    now = int(time.time() * 1000)
    owner = f"person:test:{uuid.uuid4().hex[:8]}"
    commits, reviews = 1500, 400
    _seed(graph, test_repo, owner_id=owner, decisions=200, commits=commits, reviews=reviews, now=now)

    started = time.perf_counter()
    rows = graph.run_named("pulse", _params(test_repo, now), timeout=20_000).records
    elapsed = time.perf_counter() - started

    assert rows, "every decision here has a risk signal (it is stale), so Pulse must return rows"
    assert elapsed < 10, f"pulse took {elapsed:.1f}s"
    latest_commit = now - 900 * DAY + commits * 1000
    latest_review = now - 800 * DAY + reviews * 1000 + 500
    assert {r["owner_last_active"] for r in rows} == {max(latest_commit, latest_review)}
    assert all(r["owner"]["id"] == owner for r in rows)
    assert all(r["active_decisions"] == 200 for r in rows)


def test_decision_without_owner_is_an_ownership_gap(graph, test_repo):
    now = int(time.time() * 1000)
    graph.query(
        "CREATE (k:ConfigKey {id: 'cfg:' + $repo + ':solo', repo: $repo, name: 'solo', key: 'solo', path: 'config.toml'}) "
        "CREATE (d:Decision {id: 'dec:' + $repo + ':config_value:solo', repo: $repo, kind: 'config_value', status: 'active', "
        "  key: 'config.toml::solo|config_value', subject: 'config.toml::solo', predicate: 'config_value', object: '1', "
        "  text: 'solo is 1', valid_from: $now, confidence: 0.9, signal: 'config_diff', created_at: $now}) "
        "CREATE (d)-[:ABOUT]->(k)",
        {"repo": test_repo, "now": now},
    )
    rows = graph.run_named("pulse", _params(test_repo, now), timeout=20_000).records
    assert len(rows) == 1
    assert rows[0]["owner"] is None
    assert rows[0]["owner_last_active"] == 0
    assert rows[0]["ownership_gap"] is True
