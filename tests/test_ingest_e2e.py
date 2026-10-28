"""End to end: the tmp fixture repo through `ingest_repo` (no GitHub, fake embedder) into a `test/<uuid>` repo
on the real Neo4j, then the graph is checked: counts, the RENAMED_FROM edge, the superseded config chain,
the ADR supersession, the REVERTS edge, idempotent re-run and a clean wipe."""

from __future__ import annotations

import argparse

import pytest

from ingest_fixture import DATES_MS, build_repo
from kyun import ids
from kyun.ingest.cli import register
from kyun.ingest.pipeline import ingest_repo

pytestmark = pytest.mark.neo4j


def test_ingest_tmp_repo_end_to_end(graph, test_repo, tmp_path):
    path = tmp_path / "repo"
    shas = build_repo(path)
    messages: list[str] = []
    summary = ingest_repo(test_repo, graph=graph, github=False, embed=True, repo_path=path, progress=messages.append)
    try:
        stats = summary["stats"]
        assert summary["commits"] == 6 and summary["head_sha"] == shas["c6"] and summary["default_branch"] == "main"
        assert stats["labels"]["Commit"] == 6 and stats["labels"]["File"] == 9 and stats["labels"]["Repo"] == 1
        assert stats["labels"]["Decision"] == 12 and stats["labels"]["Document"] == 3 and stats["labels"]["Dependency"] == 1
        assert stats["labels"]["Symbol"] == 5 and stats["labels"]["ConfigKey"] == 4 and stats["labels"]["Module"] == 5
        assert stats["relationship_types"]["RENAMED_FROM"] == 1 and stats["relationship_types"]["REVERTS"] == 1
        assert stats["relationship_types"]["TOUCHED"] == 16 and stats["relationship_types"]["IN"] == 13
        # Person carries no `repo` (CONTRACTS section 2), so edges leaving a Person are outside repo-scoped stats: count them directly
        assert graph.read("MATCH (:Person)-[:AUTHORED]->(c:Commit {repo: $repo}) RETURN count(*) AS n", {"repo": test_repo}).scalar() == 6
        assert summary["decisions"] == {"recorded": 12, "superseded": 5, "links_requested": summary["decisions"]["links_requested"], "linked": summary["decisions"]["links_requested"]}
        assert any(m.startswith("[write]") for m in messages)

        rename = graph.read(
            "MATCH (a:File)-[r:RENAMED_FROM]->(b:File) WHERE a.repo = $repo RETURN a.path AS new, b.path AS old, r.sha AS sha, a.alive AS alive, b.alive AS dead",
            {"repo": test_repo},
        ).records
        assert rename == [{"new": "cmd/server.go", "old": "cmd/main.go", "sha": shas["c4"], "alive": True, "dead": False}]

        chain = graph.read(
            "MATCH (d:Decision {repo: $repo, key: $key}) RETURN d.object AS object, d.status AS status, d.valid_from AS vf, d.valid_to AS vt ORDER BY d.valid_from",
            {"repo": test_repo, "key": "config/app.yaml::app.retry_limit|config_value"},
        ).records
        assert chain == [
            {"object": "3", "status": "superseded", "vf": DATES_MS[0], "vt": DATES_MS[1]},
            {"object": "5", "status": "superseded", "vf": DATES_MS[1], "vt": DATES_MS[4]},
            {"object": "3", "status": "active", "vf": DATES_MS[4], "vt": None},
        ]
        edges = graph.read(
            "MATCH (n:Decision {repo: $repo})-[s:SUPERSEDES]->(o:Decision) RETURN n.kind AS kind, n.object AS newer, o.object AS older, s.signal AS signal ORDER BY s.signal, newer, older",
            {"repo": test_repo},
        ).records
        assert {"kind": "config_value", "newer": "5", "older": "3", "signal": "config_diff"} in edges
        assert {"kind": "config_value", "newer": "3", "older": "5", "signal": "config_diff"} in edges
        assert {"kind": "config_value", "newer": "20", "older": "10", "signal": "config_diff"} in edges
        assert {"kind": "dependency", "newer": "v1.10.9", "older": "v1.10.0", "signal": "config_diff"} in edges or \
            {"kind": "dependency", "newer": "v1.10.9", "older": "v1.10.0", "signal": "lockfile_diff"} in edges
        assert {"kind": "adr", "newer": "accepted", "older": "superseded", "signal": "adr_status"} in edges
        reverts = [e for e in edges if e["signal"] == "revert_commit"]
        assert sorted(e["older"] for e in reverts) == ["20", "5"] and all(e["kind"] == "revert" for e in reverts)
        assert not any(e["signal"] == "late_import" for e in edges)

        why = graph.read(
            "MATCH (d:Decision {repo: $repo, kind: 'config_value', status: 'active', key: $key}) "
            "OPTIONAL MATCH (d)-[:IMPLEMENTED_BY]->(c:Commit) OPTIONAL MATCH (d)-[:STATED_BY]->(p:Person) OPTIONAL MATCH (d)-[:ABOUT]->(k:ConfigKey) "
            "RETURN d.text AS text, c.title AS commit, p.name AS person, k.current_value AS value, k.current_since AS since",
            {"repo": test_repo, "key": "config/app.yaml::app.retry_limit|config_value"},
        ).records[0]
        assert why == {"text": "`app.retry_limit` in `config/app.yaml` is `3`", "commit": 'Revert "Raise retry limit"', "person": "Ada Lovelace", "value": "3", "since": DATES_MS[4]}

        adr = graph.read(
            "MATCH (old:Document {repo: $repo})-[:SUPERSEDED_BY]->(new:Document) RETURN old.adr_number AS old, new.adr_number AS new, old.status AS status",
            {"repo": test_repo},
        ).records
        assert adr == [{"old": 1, "new": 2, "status": "superseded"}]
        revert = graph.read(
            "MATCH (c:Commit {repo: $repo})-[:REVERTS]->(t:Commit) RETURN c.is_revert AS flag, c.reverts_sha AS sha, t.sha AS target", {"repo": test_repo}
        ).records
        assert revert == [{"flag": True, "sha": shas["c2"], "target": shas["c2"]}]
        dep = graph.read("MATCH (d:Dependency {id: $id}) RETURN d.current_version AS v, d.ecosystem AS eco", {"id": ids.dependency_id(test_repo, "go", "github.com/lib/pq")}).records
        assert dep == [{"v": "v1.10.9", "eco": "go"}]
        symbols = graph.read("MATCH (s:Symbol {repo: $repo})-[:DEFINED_IN]->(f:File) RETURN s.name AS name, s.kind AS kind, f.path AS path ORDER BY s.line", {"repo": test_repo}).records
        assert [(s["name"], s["kind"]) for s in symbols] == [("retryLimit", "const"), ("Server", "class"), ("Run", "method"), ("healthz", "function"), ("main", "function")]
        assert all(s["path"] == "cmd/server.go" for s in symbols)
        chunk = graph.read("MATCH (c:Chunk {repo: $repo})-[:FROM]->(s) RETURN size(c.embedding) AS dim, labels(s)[0] AS src LIMIT 1", {"repo": test_repo}).records
        assert chunk and chunk[0]["dim"] == 384 and chunk[0]["src"] in ("Commit", "Document")
        person = graph.read("MATCH (i:Identity {id: $id})-[:IDENTITY_OF]->(p:Person) RETURN p.id AS pid, p.name AS name", {"id": "identity:email:ada@example.com"}).records
        assert person == [{"pid": "person:email:ada@example.com", "name": "Ada Lovelace"}]

        again = ingest_repo(test_repo, graph=graph, github=False, embed=True, repo_path=path, progress=lambda m: None)
        assert again["stats"] == stats
    finally:
        graph.query("MATCH (p:Person {id: 'person:email:ada@example.com'}) OPTIONAL MATCH (i:Identity)-[:IDENTITY_OF]->(p) DETACH DELETE i, p")
    deleted = graph.wipe_repo(test_repo)
    assert deleted == stats["nodes"]
    assert graph.read("MATCH (n {repo: $repo}) RETURN count(n) AS n", {"repo": test_repo}).scalar() == 0
    assert graph.stats(test_repo) == {"nodes": 0, "relationships": 0, "labels": {}, "relationship_types": {}}


def test_cli_registers_ingest_subcommand():
    parser = argparse.ArgumentParser()
    register(parser.add_subparsers(dest="cmd"))
    args = parser.parse_args(["ingest", "knadh/listmonk", "--max-commits", "50", "--since", "2024-01-01", "--no-github", "--no-embed", "--reset", "--max-prs", "5", "--llm-prs", "2"])
    assert (args.cmd, args.repo, args.max_commits, args.since, args.no_github, args.no_embed, args.reset, args.max_prs, args.llm_prs) == (
        "ingest", "knadh/listmonk", 50, "2024-01-01", True, True, True, 5, 2
    )
    assert callable(args.func)
