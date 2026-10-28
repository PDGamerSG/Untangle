"""Shared fixture data for the answer tests: one small repository history, available both as in-memory projection
rows (offline tests of dossiers, confidence and composition) and as plain-Cypher seeds for a `test/<uuid>` repo
(Neo4j tests). The story: `app.concurrency` in `config.toml` was 5 (commit 3fa2c1d, 2021), then 10 (PR #812 after
incident #790, March 2023)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from kyun import ids
from kyun.answer.retrieve import Dossier, Evidence, PersonToAsk, build_dossiers, version_from_row
from kyun.answer.router import ResolvedEntity, route
from kyun.embed import FakeEmbedder
from kyun.graph.db import Graph


def ms(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> int:
    return int(datetime(y, m, d, hh, mm, tzinfo=UTC).timestamp() * 1000)


T_OLD = ms(2021, 6, 2, 9, 0)
T_ISSUE = ms(2023, 3, 10, 8, 0)
T_COMMENT = ms(2023, 3, 13, 15, 0)
T_NEW = ms(2023, 3, 14, 10, 22)
T_NOW = ms(2024, 1, 15, 12, 0)

SHA_OLD = "3fa2c1d9e8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3"
SHA_NEW = "9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c"
KEY = "config.toml::app.concurrency|config_value"


class Fixture:
    """Ids for one repo. `suffix` keeps Person nodes (which carry no `repo`) unique per test repo."""

    def __init__(self, repo: str, suffix: str = ""):
        self.repo = repo
        self.login = f"knadh{suffix}"
        self.reviewer_login = f"rhea{suffix}"
        self.person = ids.person_id(login=self.login)
        self.reviewer = ids.person_id(login=self.reviewer_login)
        self.file = ids.file_id(repo, "config.toml")
        self.other_file = ids.file_id(repo, "internal/mail/sender.go")
        self.cfg = ids.config_key_id(repo, "config.toml", "app.concurrency")
        self.pr = ids.pr_id(repo, 812)
        self.issue = ids.issue_id(repo, 790)
        self.comment = ids.comment_id(repo, "pr_review", 5551)
        self.commit_old = ids.commit_id(repo, SHA_OLD)
        self.commit_new = ids.commit_id(repo, SHA_NEW)
        self.dec_old = ids.decision_id(repo, "config_value", KEY, ids.short_sha(SHA_OLD))
        self.dec_new = ids.decision_id(repo, "config_value", KEY, "812")

    # -- in-memory projection rows (what 31_decisions_about returns) ------------------------------------------------
    def about(self) -> list[dict[str, Any]]:
        return [
            {"id": self.cfg, "labels": ["ConfigKey"], "name": "app.concurrency", "path": "config.toml", "key": "app.concurrency"},
            {"id": self.file, "labels": ["File"], "name": "config.toml", "path": "config.toml", "key": None},
        ]

    def row_old(self) -> dict[str, Any]:
        return {
            "id": self.dec_old, "kind": "config_value", "key": KEY, "subject": "config.toml::app.concurrency", "predicate": "config_value",
            "object": "5", "text": "app.concurrency in config.toml is 5 (set in commit 3fa2c1d)", "rationale": None, "status": "superseded",
            "valid_from": T_OLD, "valid_to": T_NEW, "created_at": T_OLD, "confidence": 0.95, "signal": "config_diff", "about": self.about(),
            "stated_by": {"id": self.person, "name": "Kailash Nadh", "login": self.login},
            "decided_in": {"id": self.commit_old, "labels": ["Commit"], "title": "Set concurrency to 5", "url": f"https://github.com/{self.repo}/commit/{SHA_OLD}", "number": None, "kind": None, "sha": SHA_OLD, "author": None, "created_at": T_OLD},
            "motivated_by": [], "implemented_by": [], "evidence": [
                {"id": self.commit_old, "labels": ["Commit"], "title": "Set concurrency to 5", "kind": None, "number": None, "sha": SHA_OLD, "url": f"https://github.com/{self.repo}/commit/{SHA_OLD}", "path": None, "speaker": None, "excerpt": "Set concurrency to 5\n\nInitial value.", "created_at": T_OLD, "author": "Kailash Nadh"},
            ],
            "supersedes": [], "superseded_by": [{"id": self.dec_new, "at": T_NOW, "signal": "config_diff"}],
        }

    def row_new(self) -> dict[str, Any]:
        return {
            "id": self.dec_new, "kind": "config_value", "key": KEY, "subject": "config.toml::app.concurrency", "predicate": "config_value",
            "object": "10", "text": "app.concurrency in config.toml is 10 (set in PR #812 after incident #790)",
            "rationale": "The SMTP provider rate-limits above 10 concurrent connections", "status": "active",
            "valid_from": T_NEW, "valid_to": None, "created_at": T_NEW, "confidence": 0.95, "signal": "config_diff", "about": self.about(),
            "stated_by": {"id": self.person, "name": "Kailash Nadh", "login": self.login},
            "decided_in": {"id": self.pr, "labels": ["PullRequest"], "title": "Limit concurrency after SMTP errors", "url": f"https://github.com/{self.repo}/pull/812", "number": 812, "kind": None, "sha": None, "author": self.login, "created_at": T_NEW},
            "motivated_by": [{"id": self.issue, "labels": ["Issue", "Incident"], "title": "SMTP errors under load", "url": f"https://github.com/{self.repo}/issues/790", "number": 790, "created_at": T_ISSUE, "excerpt": "Mail sending fails with 421 too many connections when campaigns run.", "is_incident": True}],
            "implemented_by": [{"id": self.commit_new, "labels": ["Commit"], "title": "Limit concurrency after SMTP errors (#812)", "url": f"https://github.com/{self.repo}/commit/{SHA_NEW}", "sha": SHA_NEW, "created_at": T_NEW, "excerpt": "Limit concurrency after SMTP errors (#812)", "author": "Kailash Nadh"}],
            "evidence": [
                {"id": self.pr, "labels": ["PullRequest"], "title": "Limit concurrency after SMTP errors", "kind": None, "number": 812, "sha": None, "url": f"https://github.com/{self.repo}/pull/812", "path": None, "speaker": None, "excerpt": "Caps app.concurrency at 10. The SMTP provider rate-limits above 10 concurrent connections. Fixes #790.", "created_at": T_NEW, "author": self.login},
                {"id": self.comment, "labels": ["Comment"], "title": None, "kind": "pr_review", "number": None, "sha": None, "url": f"https://github.com/{self.repo}/pull/812#pullrequestreview-5551", "path": None, "speaker": None, "excerpt": "LGTM, 10 matches what the provider told us on the call.", "created_at": T_COMMENT, "author": self.reviewer_login},
            ],
            "supersedes": [self.dec_old], "superseded_by": [],
        }

    def entities(self) -> list[ResolvedEntity]:
        return [
            ResolvedEntity(id=self.cfg, label="ConfigKey", name="app.concurrency", path="config.toml", key="app.concurrency", strength=1.0, lucene_score=5.0, matched=True, extra={"current_value": "10"}),
            ResolvedEntity(id=self.file, label="File", name="config.toml", path="config.toml", key=None, strength=1.0, lucene_score=3.0, matched=True),
        ]

    def people(self) -> list[PersonToAsk]:
        return [PersonToAsk(id=self.person, name="Kailash Nadh", login=self.login, score=1.6, counts={"commit": 2, "decision": 2}, total_commits=2, total_prs=1)]

    def dossiers(self) -> list[Dossier]:
        versions = {}
        for row in (self.row_old(), self.row_new()):
            v = version_from_row(row)
            v.score = 0.02
            versions[v.id] = v
        return build_dossiers(versions)

    def evidence(self, question: str = "why is app.concurrency 10 in config.toml?", *, at: str | None = None, with_dossiers: bool = True, with_people: bool = True) -> Evidence:
        decision = route(question, at=at)
        ev = Evidence(repo=self.repo, question=question, decision=decision, entities=self.entities(), route=f"entity_{decision.intent}")
        if with_dossiers:
            ev.dossiers = self.dossiers()
        if with_people:
            ev.people = self.people()
        return ev


# -- Neo4j seeds ---------------------------------------------------------------------------------------------------

_SEED = """
CREATE (r:Repo {id: $repo_id, repo: $repo, full_name: $repo, url: 'https://github.com/' + $repo, default_branch: 'master', head_sha: $sha_new,
                ingested_at: $now, commit_count: 2, languages: ['Go']})
MERGE (p:Person {id: $person}) SET p.name = 'Kailash Nadh', p.login = $login, p.tokens = 'kailash nadh', p.kind = 'contributor'
MERGE (p2:Person {id: $reviewer}) SET p2.name = 'Rhea Mehta', p2.login = $reviewer_login, p2.tokens = 'rhea mehta', p2.kind = 'contributor'
CREATE (f:File {id: $file, repo: $repo, path: 'config.toml', name: 'config.toml', ext: 'toml', tokens: 'config toml', is_config: true,
                is_doc: false, alive: true, first_seen_at: $t_old, last_touched_at: $t_new, touch_count: 2})
CREATE (f2:File {id: $other_file, repo: $repo, path: 'internal/mail/sender.go', name: 'sender.go', ext: 'go', tokens: 'internal mail sender go',
                 is_config: false, is_doc: false, alive: true, first_seen_at: $t_new, last_touched_at: $t_new, touch_count: 1})
CREATE (k:ConfigKey {id: $cfg, repo: $repo, key: 'app.concurrency', path: 'config.toml', tokens: 'app concurrency', current_value: '10', current_since: $t_new})
CREATE (k)-[:SET_IN]->(f)
CREATE (pr:PullRequest {id: $pr, repo: $repo, number: 812, title: 'Limit concurrency after SMTP errors',
                        body: 'Caps app.concurrency at 10. The SMTP provider rate-limits above 10 concurrent connections. Fixes #790.',
                        state: 'closed', merged: true, created_at: $t_comment, merged_at: $t_new, closed_at: $t_new,
                        url: 'https://github.com/' + $repo + '/pull/812', author_login: $login, labels: ['bug'], additions: 3, deletions: 1, changed_files: 2})
CREATE (i:Issue:Incident {id: $issue, repo: $repo, number: 790, title: 'SMTP errors under load',
                          body: 'Mail sending fails with 421 too many connections when campaigns run.', state: 'closed', labels: ['incident'],
                          created_at: $t_issue, closed_at: $t_new, url: 'https://github.com/' + $repo + '/issues/790', author_login: $reviewer_login, is_incident: true})
CREATE (c:Comment {id: $comment, repo: $repo, kind: 'pr_review', body: 'LGTM, 10 matches what the provider told us on the call.', created_at: $t_comment,
                   url: 'https://github.com/' + $repo + '/pull/812#pullrequestreview-5551', author_login: $reviewer_login, review_state: 'APPROVED'})
CREATE (c1:Commit {id: $commit_old, repo: $repo, sha: $sha_old, title: 'Set concurrency to 5', message: 'Set concurrency to 5\\n\\nInitial value.',
                   authored_at: $t_old, committed_at: $t_old, is_merge: false, is_revert: false, url: 'https://github.com/' + $repo + '/commit/' + $sha_old,
                   additions: 1, deletions: 1, files_changed: 1})
CREATE (c2:Commit {id: $commit_new, repo: $repo, sha: $sha_new, title: 'Limit concurrency after SMTP errors (#812)',
                   message: 'Limit concurrency after SMTP errors (#812)\\n\\nFixes #790.', authored_at: $t_new, committed_at: $t_new, is_merge: false,
                   is_revert: false, url: 'https://github.com/' + $repo + '/commit/' + $sha_new, additions: 3, deletions: 1, files_changed: 2})
CREATE (p)-[:AUTHORED]->(c1), (p)-[:AUTHORED]->(c2), (p)-[:COMMITTED]->(c1), (p)-[:COMMITTED]->(c2)
CREATE (c1)-[:TOUCHED {change: 'M', additions: 1, deletions: 1}]->(f)
CREATE (c2)-[:TOUCHED {change: 'M', additions: 2, deletions: 1}]->(f), (c2)-[:TOUCHED {change: 'M', additions: 1, deletions: 0}]->(f2)
CREATE (c2)-[:PART_OF]->(pr), (pr)-[:TOUCHED]->(f), (pr)-[:TOUCHED]->(f2)
CREATE (p)-[:OPENED]->(pr), (p2)-[:OPENED]->(i), (p2)-[:REVIEWED {state: 'APPROVED', at: $t_comment}]->(pr)
CREATE (c)-[:ON]->(pr), (p2)-[:WROTE]->(c), (c)-[:ABOUT_LINE]->(f)
CREATE (pr)-[:CLOSES]->(i), (c2)-[:REFERENCES]->(i)
"""

_CHUNKS = """
UNWIND $chunks AS ch
CREATE (x:Chunk {id: ch.id, repo: $repo, text: ch.text, source_id: ch.source_id, source_kind: ch.source_kind, seq: ch.seq,
                 created_at: ch.created_at, embedding: ch.embedding})
WITH x, ch
MATCH (s {id: ch.source_id})
CREATE (x)-[:FROM]->(s)
"""


def seed_graph(graph: Graph, repo: str, *, suffix: str = "") -> Fixture:
    """Create the fixture repo with plain Cypher, then the two decisions through 21/22 so the chain is real."""
    fx = Fixture(repo, suffix)
    now = int(time.time() * 1000)
    graph.query(
        _SEED,
        {
            "repo_id": ids.repo_id(repo), "repo": repo, "now": now, "person": fx.person, "login": fx.login, "reviewer": fx.reviewer,
            "reviewer_login": fx.reviewer_login, "file": fx.file, "other_file": fx.other_file, "cfg": fx.cfg, "pr": fx.pr, "issue": fx.issue,
            "comment": fx.comment, "commit_old": fx.commit_old, "commit_new": fx.commit_new, "sha_old": SHA_OLD, "sha_new": SHA_NEW,
            "t_old": T_OLD, "t_issue": T_ISSUE, "t_comment": T_COMMENT, "t_new": T_NEW,
        },
    )
    embedder = FakeEmbedder(384)
    texts = [
        (fx.pr, "pr", "Limit concurrency after SMTP errors. Caps app.concurrency at 10. The SMTP provider rate-limits above 10 concurrent connections. Fixes #790."),
        (fx.issue, "issue", "SMTP errors under load. Mail sending fails with 421 too many connections when campaigns run."),
        (fx.commit_old, "commit", "Set concurrency to 5. Initial value."),
    ]
    chunks = [
        {"id": ids.chunk_id(src, 0), "text": text, "source_id": src, "source_kind": kind, "seq": 0, "created_at": T_NEW, "embedding": embedder.embed_one(text)}
        for src, kind, text in texts
    ]
    graph.query(_CHUNKS, {"repo": repo, "chunks": chunks})
    rows = [
        {"id": fx.dec_old, "repo": repo, "kind": "config_value", "key": KEY, "subject": "config.toml::app.concurrency", "predicate": "config_value",
         "object": "5", "text": "app.concurrency in config.toml is 5 (set in commit 3fa2c1d)", "rationale": None, "valid_from": T_OLD,
         "confidence": 0.95, "signal": "config_diff", "created_at": T_OLD},
        {"id": fx.dec_new, "repo": repo, "kind": "config_value", "key": KEY, "subject": "config.toml::app.concurrency", "predicate": "config_value",
         "object": "10", "text": "app.concurrency in config.toml is 10 (set in PR #812 after incident #790)",
         "rationale": "The SMTP provider rate-limits above 10 concurrent connections", "valid_from": T_NEW, "confidence": 0.95,
         "signal": "config_diff", "created_at": T_NEW},
    ]
    for row in rows:  # oldest first, as chronological ingestion would, so the SUPERSEDES signal is the row's own
        graph.run_named("record_decision", {"rows": [row], "now": now}, write=True)
    links = [
        (fx.dec_old, "ABOUT", fx.cfg), (fx.dec_old, "ABOUT", fx.file), (fx.dec_old, "DECIDED_IN", fx.commit_old), (fx.dec_old, "STATED_BY", fx.person),
        (fx.dec_old, "EVIDENCED_BY", fx.commit_old), (fx.dec_old, "IMPLEMENTED_BY", fx.commit_old),
        (fx.dec_new, "ABOUT", fx.cfg), (fx.dec_new, "ABOUT", fx.file), (fx.dec_new, "DECIDED_IN", fx.pr), (fx.dec_new, "STATED_BY", fx.person),
        (fx.dec_new, "MOTIVATED_BY", fx.issue), (fx.dec_new, "IMPLEMENTED_BY", fx.commit_new), (fx.dec_new, "EVIDENCED_BY", fx.pr),
        (fx.dec_new, "EVIDENCED_BY", fx.comment),
    ]
    graph.run_named("link_decision", {"rows": [{"decision_id": d, "rel": r, "target_id": t, "props": {}} for d, r, t in links], "now": now}, write=True)
    return fx


def unseed_people(graph: Graph, fx: Fixture) -> None:
    graph.query("MATCH (p:Person) WHERE p.id IN $ids DETACH DELETE p", {"ids": [fx.person, fx.reviewer]})
