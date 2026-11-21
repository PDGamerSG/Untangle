"""Sign in with GitHub and the per-person repository list."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
import respx

from untangle.api import main as api
from untangle.auth import github
from untangle.auth import service as accounts
from untangle.config import settings

ORIGIN = "http://untangle.test"


@pytest.fixture
def oauth(monkeypatch):
    monkeypatch.setenv("GITHUB_OAUTH_APPS", json.dumps({ORIGIN: {"client_id": "cid", "client_secret": "csecret"}}))
    monkeypatch.setenv("UNTANGLE_TRUSTED_ORIGINS", ORIGIN)
    monkeypatch.setenv("UNTANGLE_COOKIE_SECURE", "0")
    settings.cache_clear()
    yield
    settings.cache_clear()


@pytest.fixture
async def anon():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url=ORIGIN) as client:
        yield client


@pytest.fixture
def clean_github_accounts(graph):
    yield
    graph.query("""MATCH (u:User) WHERE u.email ENDS WITH '@auth.test' OR u.email ENDS WITH '@users.noreply.github.com'
      OPTIONAL MATCH (u)-[:HAS_SESSION]->(s:Session) OPTIONAL MATCH (u)-[:SAVED]->(r:SavedRepository)
      DETACH DELETE s, r, u""")
    accounts.clear_cache()


def _profile(**extra):
    return {"id": int(uuid.uuid4().int % 10**9), "login": f"octo{uuid.uuid4().hex[:6]}", "name": "Octo Cat",
            "avatar_url": "https://avatars.example/1", "email": None, **extra}


# -- without a database ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("value,want", [
    ("/repositories", "/repositories"), ("/ask?repo=a/b", "/ask?repo=a/b"), (None, "/repositories"),
    ("//evil.test", "/repositories"), ("https://evil.test", "/repositories"), ("/\\evil.test", "/repositories"),
])
def test_next_path_cannot_leave_the_site(value, want):
    assert github.safe_next(value) == want


def test_apps_are_read_per_origin_and_ignore_bad_config(oauth, monkeypatch):
    assert github.app_for(ORIGIN + "/").client_id == "cid"
    assert github.app_for("https://other.test") is None
    monkeypatch.setenv("GITHUB_OAUTH_APPS", "not json")
    settings.cache_clear()
    assert github.apps() == {}


@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_start_redirects_to_github_with_state_cookie(oauth, anon):
    response = await anon.get("/auth/github/start", params={"next": "/repositories"})
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=cid" in location and "redirect_uri=http%3A%2F%2Funtangle.test%2Fapi%2Fauth%2Fgithub%2Fcallback" in location
    assert "csecret" not in location
    cookie = response.headers["set-cookie"]
    assert "untangle_github=" in cookie and "HttpOnly" in cookie


@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_start_without_configuration_returns_to_sign_in(anon, monkeypatch):
    monkeypatch.delenv("GITHUB_OAUTH_APPS", raising=False)
    settings.cache_clear()
    response = await anon.get("/auth/github/start")
    assert response.status_code == 303 and response.headers["location"] == "/login?error=github-unavailable"
    assert (await anon.get("/auth/providers")).json() == {"github": False}


@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_callback_rejects_a_mismatched_state(oauth, anon):
    anon.cookies.set("untangle_github", "expected|/repositories")
    response = await anon.get("/auth/github/callback", params={"code": "abc", "state": "forged"})
    assert response.status_code == 303 and response.headers["location"] == "/login?error=github-expired"


@respx.mock
def test_profile_uses_the_verified_primary_email():
    respx.get("https://api.github.com/user").respond(200, json={"id": 7, "login": "Octo", "name": "", "avatar_url": "a"})
    respx.get("https://api.github.com/user/emails").respond(200, json=[
        {"email": "unverified@x.test", "primary": False, "verified": False},
        {"email": "Main@X.test", "primary": True, "verified": True}])
    assert github.fetch_profile("token")["email"] == "main@x.test"


@respx.mock
def test_code_exchange_failure_is_reported_without_details():
    respx.post(github.TOKEN_URL).respond(200, json={"error": "bad_verification_code"})
    with pytest.raises(accounts.AuthProblem) as error:
        github.exchange_code(github.OAuthApp("cid", "csecret"), ORIGIN, "code")
    assert error.value.status == 400 and "csecret" not in str(error.value)


# -- with a database ---------------------------------------------------------------------------------------------------


@pytest.mark.neo4j
def test_github_sign_in_creates_then_reuses_one_account(graph, clean_github_accounts):
    profile = _profile()
    first, token = github.sign_in(graph, profile, current=None, ip="10.9.0.1")
    again, _ = github.sign_in(graph, {**profile, "login": "renamed"}, current=None, ip="10.9.0.1")
    assert first.id == again.id and token
    assert first.email.endswith("@users.noreply.github.com")
    assert graph.read("MATCH (u:User {id:$id}) RETURN u.github_login AS l, u.password_hash AS p", {"id": first.id}).records[0] == {"l": "renamed", "p": None}
    # A GitHub-only account cannot be signed into with any password.
    with pytest.raises(accounts.AuthProblem):
        accounts.sign_in(graph, first.email, "anything-long-enough-1", ip="10.9.0.1")


@pytest.mark.neo4j
def test_github_links_to_the_signed_in_account_and_matching_email(graph, clean_github_accounts):
    email = f"user-{uuid.uuid4().hex[:8]}@auth.test"
    user, _ = accounts.register(graph, email, "correct horse battery staple", "Asha", ip="10.9.0.2")
    linked, _ = github.sign_in(graph, _profile(email=email), current=None, ip="10.9.0.2")
    assert linked.id == user.id
    other, _ = accounts.register(graph, f"user-{uuid.uuid4().hex[:8]}@auth.test", "correct horse battery staple", "Ravi", ip="10.9.0.2")
    connected, _ = github.sign_in(graph, _profile(), current=other, ip="10.9.0.2")
    assert connected.id == other.id
    with pytest.raises(accounts.AuthProblem) as error:
        github.sign_in(graph, _profile(), current=other, ip="10.9.0.2")
    assert error.value.status == 409
    assert github.identity(graph, other)["login"].startswith("octo")
    assert github.disconnect(graph, other) and github.identity(graph, other) is None


@pytest.mark.neo4j
def test_saved_repositories_are_private_to_each_account(graph, clean_github_accounts, test_repo):
    from untangle.repositories import mine
    a, _ = github.sign_in(graph, _profile(), current=None, ip="10.9.0.3")
    b, _ = github.sign_in(graph, _profile(), current=None, ip="10.9.0.3")
    mine.save(graph, a, test_repo)
    mine.save(graph, a, test_repo)
    assert [r["repo"] for r in mine.saved_repositories(graph, a)["repositories"]] == [test_repo]
    assert mine.saved_repositories(graph, b)["repositories"] == []
    assert mine.unsave(graph, a, test_repo)
    assert mine.saved_repositories(graph, a)["repositories"] == []
    mine.save(graph, b, test_repo)
    accounts.delete_account(graph, b)
    assert graph.read("MATCH (s:SavedRepository {repo_key:$k}) RETURN count(s)", {"k": test_repo.lower()}).scalar() == 0


@pytest.mark.neo4j
@respx.mock
def test_changes_compare_indexed_head_with_github(graph, clean_github_accounts, test_repo):
    from untangle.repositories import mine
    mine.clear_cache()
    graph.query("MERGE (r:Repo {id:$id}) SET r.full_name=$repo, r.repo=$repo, r.head_sha='aaa111', r.default_branch='main', r.ingested_at=1700000000000",
                {"id": f"repo:{test_repo}", "repo": test_repo})
    respx.get(f"https://api.github.com/repos/{test_repo}/compare/aaa111...main").respond(200, json={
        "ahead_by": 2, "behind_by": 0, "html_url": "https://github.com/x/compare",
        "commits": [{"sha": "bbb222", "html_url": "u1", "author": {"login": "asha"}, "commit": {"message": "first\n\nbody", "author": {"name": "Asha", "date": "2026-11-20T10:00:00Z"}}},
                    {"sha": "ccc333", "html_url": "u2", "author": None, "commit": {"message": "second", "author": {"name": "Ravi", "date": "2026-11-21T10:00:00Z"}}}],
        "files": [{"filename": "app.py", "status": "modified", "additions": 3, "deletions": 1}]})
    user, _ = github.sign_in(graph, _profile(), current=None, ip="10.9.0.4")
    mine.save(graph, user, test_repo)
    listed = mine.saved_repositories(graph, user)["repositories"][0]
    assert listed["changes"]["ahead_by"] == 2 and listed["unseen"] is True
    result = mine.changes(graph, user, test_repo)
    assert [c["short"] for c in result["commits"]] == ["ccc333", "bbb222"]
    assert result["commits"][1]["message"] == "first" and result["commits"][0]["author"] == "Ravi"
    assert result["files"][0]["path"] == "app.py"
    assert mine.saved_repositories(graph, user)["repositories"][0]["unseen"] is False
