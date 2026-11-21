"""Pre-flight checks: diff parsing and value matching offline, then the whole check against the fixture graph, whose
story is `app.concurrency` going from 5 to 10 in PR #812 after incident #790."""

from __future__ import annotations

import uuid

import httpx
import pytest

from _answer_fixture import Fixture, seed_graph, unseed_people
from untangle import advisories
from untangle.answer import service
from untangle.preflight import assignment, is_test, parse_change, plain, preflight, prose_value

DIFF = """Restore the old concurrency.

diff --git a/config.toml b/config.toml
index 1111111..2222222 100644
--- a/config.toml
+++ b/config.toml
@@ -1,3 +1,3 @@
 [app]
-concurrency = 10
+concurrency = 5
 -- not a header, just a line that starts with two dashes
"""


# -- parsing -----------------------------------------------------------------------------------------------------------


def test_parse_change_splits_files_lines_and_prose():
    parsed = parse_change(DIFF)
    assert parsed.is_diff and list(parsed.files) == ["config.toml"]
    fc = parsed.files["config.toml"]
    assert fc.status == "modified" and fc.added == ["concurrency = 5"] and fc.removed == ["concurrency = 10"]
    assert parsed.prose == "Restore the old concurrency."


def test_hunk_counts_keep_dash_lines_inside_the_hunk():
    text = "--- a/x.sql\n+++ b/x.sql\n@@ -1,2 +1,1 @@\n--- comment that was removed\n context\n"
    fc = parse_change(text).files["x.sql"]
    assert fc.removed == ["-- comment that was removed"] and fc.added == []


def test_new_and_deleted_files_and_named_paths():
    text = ("diff --git a/new.py b/new.py\nnew file mode 100644\n--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+x = 1\n"
            "diff --git a/old.py b/old.py\ndeleted file mode 100644\n--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-y = 2\n")
    parsed = parse_change(text, ["./lib/app.js", "new.py"])
    assert parsed.files["new.py"].status == "added" and parsed.files["old.py"].status == "deleted"
    assert parsed.files["lib/app.js"].status == "named"


@pytest.mark.parametrize(("line", "name", "value"), [
    ("concurrency = 5", "concurrency", "5"),
    ('    "cookie": "0.6.0",', "cookie", "0.6.0"),
    ("  node_js: \"0.10\"  # oldest supported", "node_js", "0.10"),
    ("requests==2.19.0", "requests", "2.19.0"),
    ("requests>=2.0", "requests", ">=2.0"),
    ("\tgithub.com/lib/pq v1.10.9", "github.com/lib/pq", "v1.10.9"),
])
def test_assignment_reads_common_formats(line, name, value):
    assert assignment([line], name) == value


def test_assignment_ignores_lines_that_do_not_set_the_name():
    assert assignment(["concurrency_limit = 4", "# concurrency"], "concurrency") is None


def test_prose_value_and_helpers():
    assert prose_value("Set app.concurrency back to 5 for the import job", "app.concurrency") == "5"
    assert prose_value("downgrade mocha to 2.1.0.", "mocha") == "2.1.0"
    assert prose_value("replace mocha with jest", "mocha") is None
    assert is_test("test/app.router.js") and is_test("pkg/x_test.go") and is_test("src/a.spec.ts") and not is_test("lib/router.js")
    assert plain("<p>Bumps [hbs](https://x) to <code>4.4</code></p>") == "Bumps hbs to 4.4"


# -- advisories (no network: a mock transport stands in for OSV.dev) -------------------------------------------------------


def test_checkable_versions():
    assert advisories.checkable("4.17.21") == advisories.Checked("4.17.21", True)
    assert advisories.checkable("^4.17.0") == advisories.Checked("4.17.0", False)
    assert advisories.checkable(">= 0.2.0") == advisories.Checked("0.2.0", False)
    assert advisories.checkable("*") is None and advisories.checkable("git+https://x") is None


def _osv(handler):
    advisories.clear_cache()
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_lookup_returns_advisories_per_version():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/querybatch"):
            queries = httpx.Request("POST", request.url, content=request.content).read()
            assert b'"ecosystem":"npm"' in queries.replace(b" ", b"")
            return httpx.Response(200, json={"results": [{"vulns": [{"id": "GHSA-aaaa"}]}, {}]})
        return httpx.Response(200, json={"id": "GHSA-aaaa", "summary": "Bad cookie names", "aliases": ["CVE-2024-1"], "published": "2024-10-04T00:00:00Z"})

    found = advisories.lookup([("npm", "cookie", "0.6.0"), ("npm", "cookie", "0.7.1")], client=_osv(handler))
    assert found.checked and found.affecting[("npm", "cookie", "0.6.0")] == ["GHSA-aaaa"] and found.affecting[("npm", "cookie", "0.7.1")] == []
    assert found.details["GHSA-aaaa"].aliases == ["CVE-2024-1"]


def test_lookup_fails_soft_and_can_be_disabled():
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    assert advisories.lookup([("npm", "cookie", "0.6.0")], client=_osv(broken)).checked is False
    off = advisories.lookup([("npm", "cookie", "0.6.0")], enabled=False)
    assert off.checked is False and "off" in (off.note or "")
    assert advisories.lookup([("other", "x", "1.0")]).checked is True  # ecosystems OSV does not know are skipped


# -- against the graph ---------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fx(graph):
    suffix = uuid.uuid4().hex[:6]
    repo = f"test/preflight{suffix}"
    fixture = seed_graph(graph, repo, suffix=suffix)
    # A small import graph: cmd/main.go -> internal/mail/sender.go, a test beside it, and a code area.
    graph.query(
        """MATCH (r:Repo {full_name: $repo}) SET r.map_head_sha = 'abc'
        WITH r
        MATCH (sender:File {repo: $repo, path: 'internal/mail/sender.go'})
        CREATE (m:File {id: $repo + ':cmd/main.go', repo: $repo, path: 'cmd/main.go', alive: true})
        CREATE (t:File {id: $repo + ':internal/mail/sender_test.go', repo: $repo, path: 'internal/mail/sender_test.go', alive: true})
        CREATE (m)-[:IMPORTS {indexer: 'repository-map-v1', line: 3}]->(sender)
        CREATE (t)-[:IMPORTS {indexer: 'repository-map-v1', line: 1}]->(sender)
        CREATE (f:Feature {id: $repo + ':feature:cmd', repo: $repo, name: 'cmd', source: 'directory'})-[:ENTRYPOINT]->(m)""",
        {"repo": repo},
    )
    yield fixture
    unseed_people(graph, fixture)
    graph.wipe_repo(repo)


@pytest.mark.neo4j
def test_a_diff_that_restores_a_replaced_value_is_flagged_with_the_incident(graph, fx: Fixture):
    res = preflight(fx.repo, DIFF, graph=graph)
    targets = {t.label: t for t in res.targets}
    assert targets["ConfigKey"].key == "app.concurrency" and targets["ConfigKey"].current == "10" and targets["ConfigKey"].proposed == "5"
    assert len(res.revivals) == 1
    revival = res.revivals[0]
    assert revival.replaced.id == fx.dec_old and revival.replaced_by.id == fx.dec_new
    assert "incident #790" in (revival.reason or "")
    assert res.review.level in ("medium", "high") and res.review.reasons[0].points == 30
    guarded = res.decisions[0]
    assert guarded.decision.id == fx.dec_new and any(g.startswith("Introduced after incident #790") for g in guarded.guards)
    assert res.people and res.people[0].login == fx.login
    assert res.next_steps[0].href == f"/decisions/{fx.dec_new}"
    assert any(c.name == "97_preflight_targets" for c in res.cypher)


@pytest.mark.neo4j
def test_a_description_alone_finds_the_key_and_the_value(graph, fx: Fixture):
    res = preflight(fx.repo, "Set app.concurrency back to 5 so imports finish faster", graph=graph)
    assert [t.key for t in res.targets if t.label == "ConfigKey"] == ["app.concurrency"]
    assert res.revivals and res.revivals[0].proposed == "5"


@pytest.mark.neo4j
def test_keeping_the_current_value_is_not_a_revival(graph, fx: Fixture):
    res = preflight(fx.repo, "Document that app.concurrency stays at 10", graph=graph)
    assert not res.revivals


@pytest.mark.neo4j
def test_reach_follows_reverse_imports_to_tests_and_areas(graph, fx: Fixture):
    res = preflight(fx.repo, "", paths=["internal/mail/sender.go", "does/not/exist.go"], graph=graph)
    assert {r.path for r in res.reach.reached} == {"cmd/main.go", "internal/mail/sender_test.go"}
    assert res.reach.tests == ["internal/mail/sender_test.go"]
    assert [a.name for a in res.reach.areas] == ["cmd"] and res.reach.areas[0].via == ["cmd/main.go", "internal/mail/sender.go"]
    assert res.unresolved_paths == ["does/not/exist.go"]
    assert any("not in the indexed snapshot" in s.text for s in res.next_steps)


@pytest.mark.neo4j
def test_nothing_matched_and_bad_input(graph, fx: Fixture):
    res = preflight(fx.repo, "Rewrite everything in a new language", graph=graph)
    assert not res.targets and res.review.score == 0 and "No indexed file" in res.limits[-1]
    with pytest.raises(ValueError):
        preflight(fx.repo, "  ", graph=graph)
    with pytest.raises(service.NotFound):
        preflight("test/not-there-at-all", "x", graph=graph)


@pytest.mark.neo4j
async def test_preflight_and_briefing_endpoints(graph, fx: Fixture):
    from untangle.api import main as api

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as client:
        r = await client.post("/preflight", json={"repo": fx.repo, "change": DIFF})
        assert r.status_code == 200, r.text
        assert r.json()["revivals"][0]["replaced_by"]["id"] == fx.dec_new
        assert (await client.post("/preflight", json={"repo": fx.repo, "change": ""})).status_code == 400
        assert (await client.post("/preflight", json={"repo": fx.repo, "change": "x" * 60_001})).status_code == 422
        b = await client.get("/briefing", params={"repo": fx.repo})
        assert b.status_code == 200, b.text
        assert b.json()["guarded"][0]["decision"]["id"] == fx.dec_new
        md = await client.get("/briefing/markdown", params={"repo": fx.repo})
        assert md.status_code == 200 and md.text.startswith(f"# Day-one briefing: {fx.repo}")
        assert "attachment" in md.headers["content-disposition"]
