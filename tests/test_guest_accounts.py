"""Trying Untangle without an account, then keeping that work by signing up or signing in."""

from __future__ import annotations

import uuid

import httpx
import pytest

from untangle.api import main as api
from untangle.auth import github, limits
from untangle.auth import service as accounts
from untangle.repositories import mine

PASSWORD = "correct horse battery staple"


def _ip() -> dict:
    return {"x-real-ip": f"10.77.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"}


@pytest.fixture
async def anon():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as client:
        yield client


@pytest.fixture
def clean(graph):
    yield
    graph.query("""MATCH (u:User) WHERE u.email ENDS WITH '@auth.test' OR u.email ENDS WITH '@guest.untangle.invalid'
      OR u.email ENDS WITH '@users.noreply.github.com'
      OPTIONAL MATCH (u)-[:HAS_SESSION]->(s:Session) OPTIONAL MATCH (u)-[:SAVED]->(r:SavedRepository)
      DETACH DELETE s, r, u""")
    accounts.clear_cache()


def test_guest_limits_are_a_quarter_of_member_limits():
    assert limits.for_guest(limits.ASK).count == 10 and limits.for_guest(limits.ASK).bucket == "ask-guest"
    assert limits.for_guest(limits.HANDOVER_UPLOAD).count == 2


@pytest.mark.neo4j
@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_guest_session_signs_in_and_sign_up_keeps_its_repositories(graph, clean, anon, test_repo):
    started = await anon.post("/auth/guest", headers=_ip())
    assert started.status_code == 201
    guest = started.json()["user"]
    assert guest["guest"] is True and guest["email"] == "" and guest["role"] == "guest"
    assert (await anon.get("/auth/me")).json()["user"]["id"] == guest["id"]
    # A second call keeps the same session instead of starting another guest.
    assert (await anon.post("/auth/guest", headers=_ip())).json()["user"]["id"] == guest["id"]

    user = accounts.resolve(graph, anon.cookies.get("untangle_session"))
    mine.save(graph, user, test_repo)
    assert (await anon.post("/auth/tokens", json={"name": "x"})).status_code == 403

    email = f"user-{uuid.uuid4().hex[:8]}@auth.test"
    upgraded = await anon.post("/auth/register", json={"email": email, "password": PASSWORD}, headers=_ip())
    assert upgraded.status_code == 201
    body = upgraded.json()["user"]
    assert body["id"] == guest["id"] and body["guest"] is False and body["email"] == email
    assert [r["repo"] for r in mine.saved_repositories(graph, accounts.resolve(graph, anon.cookies.get("untangle_session")))["repositories"]] == [test_repo]


@pytest.mark.neo4j
@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_signing_in_as_a_guest_moves_the_guest_work_to_the_account(graph, clean, anon, test_repo):
    email = f"user-{uuid.uuid4().hex[:8]}@auth.test"
    member, _ = accounts.register(graph, email, PASSWORD, "Asha", ip="10.78.0.1")
    await anon.post("/auth/guest", headers=_ip())
    guest = accounts.resolve(graph, anon.cookies.get("untangle_session"))
    mine.save(graph, guest, test_repo)
    signed = await anon.post("/auth/login", json={"email": email, "password": PASSWORD}, headers=_ip())
    assert signed.status_code == 200 and signed.json()["user"]["id"] == member.id
    assert [r["repo"] for r in mine.saved_repositories(graph, member)["repositories"]] == [test_repo]
    assert graph.read("MATCH (u:User {id:$id}) RETURN count(u)", {"id": guest.id}).scalar() == 0


@pytest.mark.neo4j
def test_guest_cannot_take_an_existing_email(graph, clean):
    email = f"user-{uuid.uuid4().hex[:8]}@auth.test"
    accounts.register(graph, email, PASSWORD, "Asha", ip="10.78.0.2")
    guest, _ = accounts.start_guest(graph, ip="10.78.0.2")
    with pytest.raises(accounts.AuthProblem) as error:
        accounts.register(graph, email, PASSWORD, None, ip="10.78.0.2", current=guest)
    assert error.value.status == 409
    with pytest.raises(accounts.AuthProblem):
        accounts.register(graph, f"guest-x@{accounts.GUEST_DOMAIN}", PASSWORD, None, ip="10.78.0.2")


@pytest.mark.neo4j
def test_github_sign_in_from_a_guest_upgrades_it(graph, clean, test_repo):
    guest, _ = accounts.start_guest(graph, ip="10.78.0.3")
    mine.save(graph, guest, test_repo)
    profile = {"id": uuid.uuid4().int % 10**9, "login": "octoguest", "name": "", "avatar_url": "", "email": None}
    user, _ = github.sign_in(graph, profile, current=guest, ip="10.78.0.3")
    assert user.id != guest.id and not user.is_guest
    assert [r["repo"] for r in mine.saved_repositories(graph, user)["repositories"]] == [test_repo]
    assert graph.read("MATCH (u:User {id:$id}) RETURN count(u)", {"id": guest.id}).scalar() == 0
