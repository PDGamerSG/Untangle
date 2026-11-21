"""Accounts, sessions, access control and request hardening.

Tests marked `real_auth` run the real session check (no signed-in test user). Database tests use unique
`@auth.test` addresses and remove every account, session and limit window they create."""

from __future__ import annotations

import time
import uuid
from dataclasses import replace

import httpx
import pytest

from untangle.answer.text import parse_at
from untangle.api import auth as auth_api
from untangle.api import main as api
from untangle.api.health import shape_health
from untangle.auth import limits, passwords
from untangle.auth import service as accounts
from untangle.config import settings
from untangle.ingest.symbols import parse_config

PASSWORD = "correct horse battery staple"


def _ip() -> dict[str, str]:
    # Each test signs up from its own address so the per-network sign-up limit does not leak between tests.
    return {"x-real-ip": f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"}


def _email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@auth.test"


@pytest.fixture
async def anon():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as c:
        yield c


@pytest.fixture
def clean_accounts(graph):
    yield
    graph.query("MATCH (u:User) WHERE u.email ENDS WITH '@auth.test' OPTIONAL MATCH (u)-[:HAS_SESSION]->(s:Session) DETACH DELETE s, u")
    graph.query("MATCH (m:Meeting) WHERE m.id STARTS WITH 'mtg:test/auth' DETACH DELETE m")
    accounts.clear_cache()


async def _register(client: httpx.AsyncClient, email: str | None = None, password: str = PASSWORD) -> httpx.Response:
    return await client.post("/auth/register", json={"email": email or _email(), "password": password, "name": "Asha"}, headers=_ip())


# -- without a database ------------------------------------------------------------------------------------------------


def test_password_policy():
    assert passwords.policy_problem("short", "a@b.co")
    assert passwords.policy_problem("password123", "a@b.co")
    assert passwords.policy_problem("aaaaaaaaaaaa", "a@b.co")
    assert passwords.policy_problem("asha.verma-2026!", "asha.verma@b.co")
    assert passwords.policy_problem("x" * 129, "a@b.co")
    assert passwords.policy_problem(PASSWORD, "a@b.co") is None


def test_password_hashes_are_salted_and_verified():
    first, second = passwords.hash_password(PASSWORD), passwords.hash_password(PASSWORD)
    assert first != second and first.startswith("$argon2id$")
    assert passwords.verify(first, PASSWORD) and not passwords.verify(first, PASSWORD + "!")
    assert not passwords.verify(None, PASSWORD) and not passwords.verify("not-a-hash", PASSWORD)


def test_emails_are_normalised_and_validated():
    assert accounts.normalize_email("  Asha@Example.COM ") == "asha@example.com"
    for bad in ("", "asha", "asha@", "@example.com", "a b@example.com", "asha@example", "x" * 250 + "@a.co"):
        with pytest.raises(accounts.AuthProblem):
            accounts.normalize_email(bad)


def test_session_tokens_are_stored_hashed():
    token = "secret-token"
    assert accounts.token_hash(token) != token and len(accounts.token_hash(token)) == 64


def test_secure_cookie_uses_the_host_prefix(monkeypatch):
    monkeypatch.setattr(auth_api, "settings", lambda: replace(settings(), cookie_secure=True))
    assert auth_api.cookie_name() == "__Host-untangle_session"
    monkeypatch.setattr(auth_api, "settings", lambda: replace(settings(), cookie_secure=False))
    assert auth_api.cookie_name() == "untangle_session"


@pytest.mark.real_auth
async def test_protected_routes_need_a_session(anon):
    for method, path in (("get", "/repos"), ("get", "/pulse?repo=o/r"), ("get", "/stats"), ("get", "/meetings?repo=o/r"),
                         ("get", "/repository-imports"), ("get", "/repository-map?repo=o/r")):
        r = await getattr(anon, method)(path)
        assert r.status_code in (401, 503), (path, r.status_code)


@pytest.mark.real_auth
async def test_cross_site_writes_are_rejected_before_anything_runs(anon):
    r = await anon.post("/auth/login", json={"email": "a@b.co", "password": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = await anon.post("/ask", json={"question": "why?", "repo": "o/r"}, headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


async def test_api_responses_carry_security_headers(anon):
    r = await anon.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"
    assert "max-age" in r.headers["strict-transport-security"]


async def test_untrusted_request_ids_are_replaced(anon):
    r = await anon.get("/health", headers={"x-request-id": "abc\r\nSet-Cookie: x=1"})
    assert r.headers["x-request-id"] != "abc" and "\n" not in r.headers["x-request-id"]
    r = await anon.get("/health", headers={"x-request-id": "trace-123"})
    assert r.headers["x-request-id"] == "trace-123"


def test_public_health_hides_hosts_models_and_errors():
    shaped = shape_health({"ok": False, "version": "0.1.0",
                           "neo4j": {"ok": False, "uri": "neo4j+s://secret.databases.neo4j.io", "version": "5", "error": "auth failed for neo4j"},
                           "llm": {"backend": "anthropic", "model": "model-id", "available": True},
                           "embed": {"backend": "fastembed", "dim": 384}, "sarvam": {"configured": True, "model": "stt"}})
    text = str(shaped)
    for secret in ("secret.databases", "model-id", "anthropic", "auth failed", "stt", "fastembed"):
        assert secret not in text
    assert shaped["status"] == "degraded" and shaped["optional_backends"]["llm"]["available"] is True


async def test_unexpected_errors_do_not_reveal_internals(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("password=hunter2 at /tmp/secret/path")

    monkeypatch.setattr(api.service, "repos", boom)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app, raise_app_exceptions=False), base_url="http://untangle.test") as c:
        r = await c.get("/repos")
    assert r.status_code == 500
    assert "hunter2" not in r.text and "/tmp/secret" not in r.text and r.json()["request_id"]


def test_dates_are_bounded():
    assert parse_at("1700000000000") == 1_700_000_000_000
    with pytest.raises(ValueError):
        parse_at("99999999999999999999999")
    with pytest.raises(ValueError):
        parse_at(-5)


def test_yaml_config_keeps_values_as_written_and_refuses_aliases():
    values = parse_config("ci.yml", "on:\n  push: true\nversion: 1.20\nmode: off\n")
    assert values["on.push"] == "true" and values["version"] == "1.20" and values["mode"] == "off"
    bomb = "a: &a [x, x, x, x]\nb: &b [*a, *a, *a, *a]\nc: [*b, *b, *b, *b]\n"
    assert parse_config("bomb.yaml", bomb) == {}


async def test_uploads_reject_unknown_formats(client_as_admin):
    r = await client_as_admin.post("/kt/ingest", data={"repo": "o/r"}, files={"audio": ("call.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415
    r = await client_as_admin.post("/kt/ingest", data={"repo": "o/r"}, files={"transcript": ("call.json", b"\xff\xfe\x00bad", "application/json")})
    assert r.status_code == 415


@pytest.fixture
async def client_as_admin():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as c:
        yield c


# -- with Neo4j -------------------------------------------------------------------------------------------------------


@pytest.mark.neo4j
@pytest.mark.real_auth
async def test_register_sign_in_session_and_sign_out(anon, graph, clean_accounts):
    email = _email()
    r = await _register(anon, email)
    assert r.status_code == 201, r.text
    assert r.json()["user"]["email"] == email and "password_hash" not in r.text
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    token = anon.cookies.get(auth_api.cookie_name())
    # Only the token's hash is stored.
    stored = graph.read("MATCH (s:Session {user_id: $id}) RETURN s.id AS id", {"id": r.json()["user"]["id"]}).records
    assert stored and token not in {row["id"] for row in stored}

    assert (await anon.get("/auth/me")).json()["user"]["email"] == email
    assert (await anon.get("/repos")).status_code == 200

    assert (await anon.post("/auth/logout")).status_code == 204
    anon.cookies.set(auth_api.cookie_name(), token)
    assert (await anon.get("/auth/me")).status_code == 401
    assert (await anon.get("/repos")).status_code == 401

    again = await anon.post("/auth/login", json={"email": email.upper(), "password": PASSWORD}, headers=_ip())
    assert again.status_code == 200 and again.json()["user"]["email"] == email


@pytest.mark.neo4j
@pytest.mark.real_auth
async def test_sign_up_rules(anon, clean_accounts):
    email = _email()
    assert (await _register(anon, email)).status_code == 201
    anon.cookies.clear()
    duplicate = await _register(anon, email.upper())
    assert duplicate.status_code == 409
    assert (await _register(anon, password="password123")).status_code == 400
    assert (await _register(anon, email="not-an-email")).status_code == 400


@pytest.mark.neo4j
@pytest.mark.real_auth
async def test_wrong_passwords_are_generic_and_locked_out(anon, clean_accounts):
    email = _email()
    assert (await _register(anon, email)).status_code == 201
    anon.cookies.clear()
    unknown = await anon.post("/auth/login", json={"email": _email(), "password": PASSWORD}, headers=_ip())
    wrong = await anon.post("/auth/login", json={"email": email, "password": "not the password"}, headers=_ip())
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]
    for _ in range(limits.SIGN_IN_FAILURES.count - 1):
        await anon.post("/auth/login", json={"email": email, "password": "still wrong"}, headers=_ip())
    locked = await anon.post("/auth/login", json={"email": email, "password": PASSWORD}, headers=_ip())
    assert locked.status_code == 429 and int(locked.headers["retry-after"]) > 0


@pytest.mark.neo4j
@pytest.mark.real_auth
async def test_members_have_question_quotas(anon, clean_accounts, monkeypatch):
    monkeypatch.setattr(limits, "ASK", limits.Limit(f"ask-test-{uuid.uuid4().hex[:6]}", 1, 3600))
    assert (await _register(anon)).status_code == 201
    first = await anon.post("/ask", json={"question": "why is retry_limit 3?", "repo": "test/auth-none"})
    assert first.status_code != 429
    second = await anon.post("/ask", json={"question": "why is retry_limit 3?", "repo": "test/auth-none"})
    assert second.status_code == 429 and second.headers.get("retry-after")


@pytest.mark.neo4j
@pytest.mark.real_auth
async def test_only_the_uploader_can_delete_a_handover_call(anon, graph, clean_accounts):
    owner = await _register(anon)
    owner_id = owner.json()["user"]["id"]
    owner_cookie = anon.cookies.get(auth_api.cookie_name())
    meeting = f"mtg:test/auth{uuid.uuid4().hex[:6]}:call"
    graph.query("CREATE (:Meeting {id: $id, repo: 'test/auth', uploaded_by: $owner, created_at: $now})",
                {"id": meeting, "owner": owner_id, "now": int(time.time() * 1000)})
    anon.cookies.clear()
    await _register(anon)
    assert (await anon.delete(f"/meetings/{meeting}")).status_code == 403
    anon.cookies.clear()
    anon.cookies.set(auth_api.cookie_name(), owner_cookie)
    assert (await anon.delete(f"/meetings/{meeting}")).status_code == 204
    assert not graph.read("MATCH (m:Meeting {id: $id}) RETURN m", {"id": meeting}).records
    assert (await anon.delete(f"/meetings/{meeting}")).status_code == 404


@pytest.mark.neo4j
@pytest.mark.real_auth
async def test_deleting_an_account_ends_its_sessions(anon, graph, clean_accounts):
    r = await _register(anon)
    user_id = r.json()["user"]["id"]
    assert (await anon.delete("/auth/account")).status_code == 204
    assert (await anon.get("/auth/me")).status_code == 401
    assert not graph.read("MATCH (s:Session {user_id: $id}) RETURN s", {"id": user_id}).records
    assert not graph.read("MATCH (u:User {id: $id}) RETURN u", {"id": user_id}).records


@pytest.mark.neo4j
def test_expired_windows_and_sessions_are_pruned(graph, clean_accounts):
    past = time.time() - 10 * 86_400
    limits.hit(graph, limits.Limit("prune-test", 5, 60), "subject", "", now=past)
    limits.prune(graph)
    assert not graph.read("MATCH (r:RateLimit) WHERE r.id STARTS WITH 'prune-test|' RETURN r").records
