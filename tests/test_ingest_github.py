"""github_api: recorded fixtures replayed with respx, the on-disk cache, rate-limit handling and incident rules."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest
import respx

from kyun.ingest.decisions import closes_numbers, mentioned_numbers, supersedes_numbers
from kyun.ingest.github_api import GitHubClient, GitHubError, is_incident, to_ms

FIXTURES = Path(__file__).parent / "fixtures" / "github"
BASE = "https://api.github.com"


def _fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _serve(request: httpx.Request) -> httpx.Response:
    path, page = request.url.path.removeprefix("/repos/acme/demo/"), request.url.params.get("page", "1")
    if page != "1":
        return httpx.Response(200, json=[])
    table = {
        "pulls": "pulls_page1.json", "issues": "issues_page1.json", "pulls/7/reviews": "pull_7_reviews.json",
        "pulls/7/comments": "pull_7_comments.json", "issues/7/comments": "issue_7_comments.json", "pulls/7/commits": "pull_7_commits.json",
        "pulls/9/commits": "pull_9_commits.json", "issues/5/comments": "issue_5_comments.json",
    }
    if path in table:
        return httpx.Response(200, json=_fixture(table[path]))
    if path.startswith(("pulls/", "issues/")):
        return httpx.Response(200, json=[])
    return httpx.Response(404, json={"message": "Not Found"})


@pytest.fixture
def mocked():
    with respx.mock(base_url=BASE, assert_all_called=False) as mock:
        mock.route().mock(side_effect=_serve)
        yield mock


def test_fetch_all_from_fixtures(mocked, tmp_path):
    with GitHubClient("acme/demo", token=False, cache_dir=tmp_path / "gh") as client:
        data = client.fetch_all(max_prs=None, progress=lambda m: None)
    assert [pr.number for pr in data.prs] == [9, 7, 4]
    pr7 = next(pr for pr in data.prs if pr.number == 7)
    assert pr7.merged and pr7.merged_at == to_ms("2024-03-01T10:00:00Z") and pr7.labels == ["database"] and pr7.author_login == "ada"
    assert [r.state for r in pr7.reviews] == ["APPROVED"] and pr7.review_comments[0].path == "go.mod" and pr7.review_comments[0].line == 7
    assert pr7.comments[0].kind == "pr_comment" and pr7.commits[0].sha == "C3SHA" and pr7.discussion_size == 3
    assert not next(pr for pr in data.prs if pr.number == 4).merged
    assert data.email_to_login == {"ada@example.com": "ada"} and data.login_names == {"ada": "Ada Lovelace"}
    assert sorted(i.number for i in data.issues) == [3, 5, 12] and data.pr_numbers == {4, 7, 9}
    incident = next(i for i in data.issues if i.number == 5)
    assert incident.is_incident and incident.comments[0].author_login == "carol" and incident.comments[0].kind == "issue_comment"
    assert not next(i for i in data.issues if i.number == 3).is_incident
    assert data.requests_made == 15 and data.cache_hits == 0


def test_cache_makes_rerun_free(mocked, tmp_path):
    with GitHubClient("acme/demo", token=False, cache_dir=tmp_path / "gh") as first:
        a = first.fetch_all(progress=lambda m: None)
    assert a.requests_made > 0 and any(tmp_path.joinpath("gh").glob("pulls*.json"))
    before = mocked.calls.call_count
    with GitHubClient("acme/demo", token=False, cache_dir=tmp_path / "gh") as second:
        b = second.fetch_all(progress=lambda m: None)
    assert b.requests_made == 0 and b.cache_hits == a.requests_made and mocked.calls.call_count == before
    assert [pr.number for pr in b.prs] == [pr.number for pr in a.prs] and b.issues[0].title == a.issues[0].title


def test_max_prs_and_pagination(mocked, tmp_path):
    with GitHubClient("acme/demo", token=False, cache_dir=tmp_path / "gh") as client:
        assert [pr.number for pr in client.pulls(max_prs=2)] == [9, 7]
        assert client.get("repos/acme/demo/releases/999") is None


def test_rate_limit_sleeps_until_reset(tmp_path):
    slept: list[float] = []
    reset = int(time.time()) + 5
    with respx.mock(base_url=BASE) as mock:
        mock.get("/repos/acme/demo/issues/3/comments").mock(side_effect=[
            httpx.Response(403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)}, json={"message": "API rate limit exceeded"}),
            httpx.Response(200, json=_fixture("issue_5_comments.json")),
        ])
        with GitHubClient("acme/demo", token=False, cache_dir=tmp_path / "gh", sleep=slept.append) as client:
            body = client.get("repos/acme/demo/issues/3/comments")
    assert len(body) == 1 and len(slept) == 1 and 3 <= slept[0] <= 8


def test_server_errors_retry_then_give_up(tmp_path):
    slept: list[float] = []
    with respx.mock(base_url=BASE) as mock:
        mock.get("/repos/acme/demo/pulls/1/reviews").mock(side_effect=[httpx.Response(502), httpx.Response(200, json=[])])
        mock.get("/repos/acme/demo/pulls/2/reviews").mock(return_value=httpx.Response(403, json={"message": "Resource not accessible"}))
        with GitHubClient("acme/demo", token=False, use_cache=False, sleep=slept.append) as client:
            assert client.get("repos/acme/demo/pulls/1/reviews") == [] and slept == [1.0]
            with pytest.raises(GitHubError):
                client.get("repos/acme/demo/pulls/2/reviews")


def test_incident_rules_and_reference_parsing():
    assert is_incident("Weekly digest", ["bug"]) and is_incident("Regression in templates", []) and is_incident("x", ["data loss"])
    assert not is_incident("Add dark mode", ["enhancement"])
    assert closes_numbers("Fixes #5, closes #7 and resolves: #9; see #11") == [5, 7, 9]
    assert closes_numbers("Closes https://github.com/acme/demo/issues/42") == [42]
    assert mentioned_numbers("see #11 and #5, not &#8203; or a/b#3") == [11, 5]
    assert supersedes_numbers("Supersedes #4. Replaces PR #6, reverts #8") == [4, 6, 8]
