"""config_history, decisions (PR change / revert / explicit supersession), LLM rationale extraction and chunking,
all on the tmp fixture repo with hand-built PR records: no network, no Neo4j."""

from __future__ import annotations

import pytest

from ingest_fixture import DATES_MS, build_repo
from kyun import ids
from kyun.ingest.chunks import build_sources, chunk_rows, chunk_text
from kyun.ingest.config_history import config_history, history_paths
from kyun.ingest.decisions import explicit_supersessions, first_paragraph, pr_change_decisions, revert_decisions
from kyun.ingest.extract_llm import extract_pr_rationales, locate_quotes, most_discussed
from kyun.ingest.git_history import GitRepo
from kyun.ingest.github_api import CommentRecord, GitHubData, PRCommitRecord, PullRecord, ReviewRecord
from kyun.ingest.loader import People, file_rows, github_rows
from kyun.llm import FakeLLM

REPO = "test/decisions"


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    path = tmp_path_factory.mktemp("repo")
    shas = build_repo(path)
    git = GitRepo(path)
    return git, shas, git.log()


def _pr(number, title, body, merged_at, shas, author="ada", reviews=(), review_comments=(), comments=()):
    return PullRecord(
        number=number, title=title, body=body, state="closed", merged=merged_at is not None, created_at=merged_at and merged_at - 1000,
        updated_at=merged_at, merged_at=merged_at, closed_at=merged_at, url=f"https://github.com/{REPO}/pull/{number}", author_login=author,
        labels=[], merge_commit_sha=None, head_sha=None, reviews=list(reviews), review_comments=list(review_comments), comments=list(comments),
        commits=[PRCommitRecord(s, "Ada Lovelace", "ada@example.com", "ada", "") for s in shas],
    )


def _prs(shas):
    review = ReviewRecord(501, "bob", "APPROVED", "LGTM, pgx is faster and the pool handles reconnects.", DATES_MS[2] - 5000, None)
    rc = CommentRecord(601, "pr_review_comment", "bob", "Pin to v1.10.9 please, v1.10.0 has the timeout bug.", DATES_MS[2] - 6000, None, path="go.mod", line=7)
    c = CommentRecord(701, "pr_comment", "ada", "Benchmarks attached: 2x throughput on the campaign queries.", DATES_MS[2] - 7000, None)
    pr7 = _pr(7, "Switch to pgx", "Closes #3\n\nSupersedes #4.\n\nlib/pq is in maintenance mode; pgx is faster.", DATES_MS[2], [shas["c3"]],
              reviews=[review], review_comments=[rc], comments=[c])
    pr9 = _pr(9, "Fix crash on startup", "Fixes #5\n\nThe server panicked when the config file was missing.", DATES_MS[5], [shas["c6"]])
    pr4 = _pr(4, "Switch to go-pg", "An earlier attempt.", DATES_MS[1], [shas["c2"]], author="bob")
    pr4.merged = True  # pretend c2 was merged through PR 4 so the revert supersedes a change decision too
    return [pr9, pr7, pr4]


def test_config_history_chains_values_and_dependencies(repo):
    git, shas, commits = repo
    paths = history_paths({fc.path for c in commits for fc in c.files})
    assert set(paths) == {"config/app.yaml", "config.toml", "go.mod"}
    pr7 = _prs(shas)[1]
    hist = config_history(REPO, git, commits, paths, pr_by_sha={shas["c3"]: pr7}, issue_numbers={3, 5, 12})
    assert hist.files_walked == 3 and hist.versions_read == 3 + 3 + 2
    retry = [r for r in hist.decisions if r.key == "config/app.yaml::app.retry_limit|config_value"]
    assert [(r.object, r.valid_from) for r in retry] == [("3", DATES_MS[0]), ("5", DATES_MS[1]), ("3", DATES_MS[4])]
    assert retry[0].text == "`app.retry_limit` in `config/app.yaml` is `3`" and retry[1].rationale == "Raise retry limit"
    assert retry[1].signal == "config_diff" and retry[1].confidence == 0.95 and retry[2].order > retry[1].order > retry[0].order
    assert ("ABOUT", ids.config_key_id(REPO, "config/app.yaml", "app.retry_limit"), {}) in retry[1].links
    assert ("IMPLEMENTED_BY", ids.commit_id(REPO, shas["c2"]), {}) in retry[1].links
    assert ("DECIDED_IN", ids.commit_id(REPO, shas["c2"]), {}) in retry[1].links
    assert ("STATED_BY", "person:email:ada@example.com", {}) in retry[1].links
    conc = [r.object for r in hist.decisions if r.key == "config.toml::app.concurrency|config_value"]
    assert conc == ["10", "20", "10"]
    deps = [r for r in hist.decisions if r.kind == "dependency"]
    assert [(r.key, r.object) for r in deps] == [("dep|github.com/lib/pq|dependency_version", "v1.10.0"), ("dep|github.com/lib/pq|dependency_version", "v1.10.9")]
    bump = deps[1]
    assert bump.rationale == "Switch to pgx (#7)" and bump.signal == "lockfile_diff" and bump.text.startswith("`github.com/lib/pq` (go) is at `v1.10.9`")
    assert ("DECIDED_IN", ids.pr_id(REPO, 7), {}) in bump.links and ("MOTIVATED_BY", ids.issue_id(REPO, 3), {}) in bump.links
    assert ("ABOUT", ids.dependency_id(REPO, "go", "github.com/lib/pq"), {}) in bump.links
    assert hist.config_keys[("config/app.yaml", "app.retry_limit")].value == "3" and hist.config_keys[("config/app.yaml", "app.retry_limit")].since == DATES_MS[4]
    assert hist.dependencies[("go.mod", "github.com/lib/pq")].value == "v1.10.9"
    assert hist.decisions == sorted(hist.decisions, key=lambda r: (r.valid_from, r.order, r.id))


def test_pr_change_revert_and_explicit_supersession(repo):
    git, shas, commits = repo
    commits_by_sha = {c.sha: c for c in commits}
    prs = _prs(shas)
    people = People({"ada@example.com": "ada"}, {"ada": "Ada Lovelace"})
    gh = GitHubData(prs=prs, pr_numbers={4, 7, 9})
    rows = github_rows(REPO, gh, commits_by_sha, people)
    assert rows.pr_commit_shas[7] == [shas["c3"]] and rows.pr_by_sha[shas["c2"]].number == 4
    assert ("person:gh:ada", "person:gh:bob") == (people.for_email("Ada Lovelace", "ada@example.com"), people.for_login("bob"))

    change = pr_change_decisions(REPO, prs, commits_by_sha, rows.pr_commit_shas, {3, 5, 12}, rows.comment_ids_by_pr, people.person_id_for_login)
    by_number = {int(r.subject[3:]): r for r in change}
    assert set(by_number) == {4, 7, 9}
    pr7 = by_number[7]
    assert pr7.kind == "change" and pr7.key == "pr#7|changed" and pr7.object == "Switch to pgx" and pr7.valid_from == DATES_MS[2]
    assert pr7.rationale == "Closes #3" or pr7.rationale.startswith("lib/pq")  # first paragraph after the closes line
    links = set((rel, t) for rel, t, _ in pr7.links)
    assert ("DECIDED_IN", ids.pr_id(REPO, 7)) in links and ("STATED_BY", "person:gh:ada") in links
    assert ("MOTIVATED_BY", ids.issue_id(REPO, 3)) in links and ("IMPLEMENTED_BY", ids.commit_id(REPO, shas["c3"])) in links
    assert ("ABOUT", ids.file_id(REPO, "go.mod")) in links and ("ABOUT", ids.file_id(REPO, "docs/adr/0002-switch-to-pgx.md")) in links
    assert ("EVIDENCED_BY", ids.comment_id(REPO, "pr_review", 501)) in links and ("EVIDENCED_BY", ids.comment_id(REPO, "pr_review_comment", 601)) in links
    assert first_paragraph("<!-- template -->\n# Title\n\n- [ ] todo\n\nReal reason here.\n\nMore.") == "Real reason here."

    assert explicit_supersessions(REPO, prs, by_number) == 1
    assert ("SUPERSEDES", by_number[4].id, {"signal": "supersedes_text", "at": DATES_MS[2]}) in pr7.links

    hist = config_history(REPO, git, commits, ["config/app.yaml"])
    by_commit: dict[str, list[str]] = {}
    for row in hist.decisions + change:
        for rel, target, _ in row.links:
            if rel == "IMPLEMENTED_BY":
                by_commit.setdefault(target, []).append(row.id)
    reverts = revert_decisions(REPO, commits, commits_by_sha, by_commit, people.person_id_for_email)
    assert len(reverts) == 1
    rv = reverts[0]
    assert rv.kind == "revert" and rv.key == f"revert|{ids.short_sha(shas['c2'])}|reverted" and rv.valid_from == DATES_MS[4] and rv.signal == "revert_commit"
    superseded = {t for rel, t, p in rv.links if rel == "SUPERSEDES" and p["signal"] == "revert_commit"}
    five = next(r for r in hist.decisions if r.object == "5")
    assert superseded == {five.id, by_number[4].id}
    assert ("EVIDENCED_BY", ids.commit_id(REPO, shas["c2"]), {}) in rv.links and ("ABOUT", ids.file_id(REPO, "config/app.yaml"), {}) in rv.links
    assert ("STATED_BY", "person:gh:ada", {}) in rv.links


def test_people_merge_email_into_login_and_file_rows(repo):
    git, shas, commits = repo
    people = People({"ada@example.com": "ada"}, {})
    pid = people.for_email("Ada Lovelace", "ADA@example.com")
    assert pid == "person:gh:ada"
    persons, identities = people.rows()
    assert persons == [{"id": "person:gh:ada", "name": "Ada Lovelace", "login": "ada", "email": "ada@example.com", "kind": "contributor", "tokens": "ada lovelace"}]
    assert {i["id"]: i["person_id"] for i in identities} == {"identity:login:ada": "person:gh:ada", "identity:email:ada@example.com": "person:gh:ada"}
    assert People().for_email("X", "x@y.z") == "person:email:x@y.z" and People().for_login(None) is None

    rows = file_rows(REPO, commits, git.files_at_head(), People())
    paths = {r["path"]: r for r in rows.files}
    assert paths["cmd/main.go"]["alive"] is False and paths["cmd/server.go"]["alive"] is True and paths["cmd/server.go"]["touch_count"] == 2
    assert paths["config/app.yaml"]["is_config"] and paths["README.md"]["is_doc"] and paths["config/app.yaml"]["first_seen_at"] == DATES_MS[0]
    assert rows.renames == [{"new_id": ids.file_id(REPO, "cmd/server.go"), "old_id": ids.file_id(REPO, "cmd/main.go"), "at": DATES_MS[3], "sha": shas["c4"]}]
    assert [m["path"] for level in rows.modules_by_depth for m in level] == [".", "cmd", "config", "docs", "docs/adr"]
    assert rows.first_author["config/app.yaml"] == "person:email:ada@example.com"


class ScriptedLLM(FakeLLM):
    backend = "scripted"


def test_llm_extraction_keeps_only_quoted_decisions(repo):
    _git, shas, _commits = repo
    prs = _prs(shas)
    reply = """{"decisions": [
      {"subject": "database driver", "predicate": "chose", "object": "jackc/pgx", "rationale": "pgx is faster and the pool handles reconnects",
       "about_paths": ["go.mod", "nope.go"], "quotes": ["pgx is faster and the pool handles reconnects"], "confidence": 0.9},
      {"subject": "lib/pq", "predicate": "deprecated", "object": "removed", "quotes": ["this sentence is not in the thread"], "confidence": 0.7}
    ]}"""
    llm = ScriptedLLM({"PR #7": reply})
    rows = extract_pr_rationales(REPO, prs, top_n=1, llm=llm, known_paths={"go.mod"}, person_id_for_login={"bob": "person:gh:bob"})
    assert [pr.number for pr in most_discussed(prs, 2)] == [7, 9]
    assert len(rows) == 1 and len(llm.calls) == 1
    row = rows[0]
    assert row.kind == "rationale" and row.key == "database driver|chose" and row.signal == "llm_pr_thread" and row.confidence == 0.8
    assert row.text == "database driver chose jackc/pgx (PR #7)" and row.valid_from == DATES_MS[2]
    assert ("EVIDENCED_BY", ids.comment_id(REPO, "pr_review", 501), {}) in row.links
    assert ("STATED_BY", "person:gh:bob", {}) in row.links and ("ABOUT", ids.file_id(REPO, "go.mod"), {}) in row.links
    assert ("DECIDED_IN", ids.pr_id(REPO, 7), {}) in row.links
    assert extract_pr_rationales(REPO, prs, top_n=1, llm=FakeLLM()) == []  # fake backend: silent no-op
    assert locate_quotes(["short"], [("x", "short text", None)]) == []


def test_chunking(repo):
    _git, _shas, commits = repo
    long = "\n\n".join(f"Paragraph {i}. " + "word " * 120 for i in range(6))
    pieces = chunk_text(long)
    assert 3 <= len(pieces) <= 8 and all(len(p) <= 800 for p in pieces) and pieces[0].startswith("Paragraph 0.")
    assert chunk_text("too short") == [] and chunk_text("x" * 2000) == ["x" * 800, "x" * 800, "x" * 400]
    sources = list(build_sources(REPO, commits=commits))
    assert len(sources) == 6 and sources[0].source_kind == "commit" and sources[0].source_id.startswith("commit:test/decisions@")
    rows = chunk_rows(REPO, sources, embedder=None)
    assert all(r["embedding"] is None and r["repo"] == REPO and r["seq"] == 0 for r in rows) and 4 <= len(rows) <= 6
    from kyun.embed import FakeEmbedder

    embedded = chunk_rows(REPO, sources, embedder=FakeEmbedder(16))
    assert all(len(r["embedding"]) == 16 for r in embedded) and embedded[0]["id"] == ids.chunk_id(embedded[0]["source_id"], 0)
