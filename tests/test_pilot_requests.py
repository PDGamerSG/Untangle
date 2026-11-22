"""The pricing page's pilot request form and the account usage readout."""

from __future__ import annotations

import uuid

import httpx
import pytest

from untangle import cli
from untangle.api import main as api
from untangle.api import pilots
from untangle.auth import limits
from untangle.auth import service as accounts

PASSWORD = "correct horse battery staple"
DOMAIN = "pilots.untangle.dev"


def _ip() -> dict:
    return {"x-real-ip": f"10.91.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"}


def _body(**extra) -> dict:
    return {"name": "Asha Verma", "email": f"lead-{uuid.uuid4().hex[:8]}@{DOMAIN}", "company": "Acme GCC", "role": "Delivery lead",
            "team_size": 18, "plan": "transition", "message": "Handover of the billing service in January.", **extra}


@pytest.fixture
async def anon():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as client:
        yield client


@pytest.fixture
def clean(graph):
    yield
    graph.query(f"MATCH (r:PilotRequest) WHERE r.email ENDS WITH '@{DOMAIN}' DETACH DELETE r")
    graph.query("""MATCH (u:User) WHERE u.email ENDS WITH '@auth.test' OR u.email ENDS WITH '@guest.untangle.invalid'
      OPTIONAL MATCH (u)-[:HAS_SESSION]->(s:Session) DETACH DELETE s, u""")
    accounts.clear_cache()


def test_reserved_example_domains_are_recognised():
    for email in ("a@example.com", "a@mail.example.org", "a@shop.test", "a@x.invalid", "a@example"):
        assert pilots.reserved(email), email
    for email in ("a@acme.com", "a@examples.com", "a@testing.io", f"a@{DOMAIN}"):
        assert not pilots.reserved(email), email


def test_references_use_unambiguous_characters():
    ref = pilots.reference()
    assert ref.startswith("UT-") and len(ref) == 9
    assert not set(ref[3:]) & set("01IOL")


@pytest.mark.neo4j
@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_visitor_request_is_stored_without_the_network_address(graph, clean, anon):
    ip = _ip()
    sent = await anon.post("/pilot-requests", json=_body(email=f"Lead.Case@{DOMAIN}", company="  Acme   GCC "), headers=ip)
    assert sent.status_code == 201
    body = sent.json()
    assert body["stored"] is True and body["plan"] == "transition" and body["reference"].startswith("UT-")
    row = graph.read("MATCH (r:PilotRequest {reference:$ref}) RETURN r {.*} AS r", {"ref": body["reference"]}).scalar()
    assert row["email"] == f"lead.case@{DOMAIN}" and row["company"] == "Acme GCC" and row["team_size"] == 18
    # Neo4j keeps no property for a null value: no account is linked.
    assert row["status"] == "new" and row.get("user_id") is None
    assert ip["x-real-ip"] not in str(row) and len(row["ip_digest"]) == 32


@pytest.mark.neo4j
@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_signed_in_request_records_the_account(graph, clean, anon):
    email = f"user-{uuid.uuid4().hex[:8]}@auth.test"
    member, _ = accounts.register(graph, email, PASSWORD, "Asha", ip="10.91.0.1")
    await anon.post("/auth/login", json={"email": email, "password": PASSWORD}, headers=_ip())
    sent = await anon.post("/pilot-requests", json=_body(plan="team"), headers=_ip())
    assert sent.status_code == 201
    stored = graph.read("MATCH (r:PilotRequest {reference:$ref}) RETURN r.user_id", {"ref": sent.json()["reference"]}).scalar()
    assert stored == member.id


@pytest.mark.neo4j
@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_example_domains_and_filled_honeypots_are_accepted_but_not_stored(graph, clean, anon):
    for body in (_body(email="live-check@example.com"), _body(website="https://spam.example")):
        sent = await anon.post("/pilot-requests", json=body, headers=_ip())
        assert sent.status_code == 201 and sent.json()["stored"] is False
        assert graph.read("MATCH (r:PilotRequest {reference:$ref}) RETURN count(r)", {"ref": sent.json()["reference"]}).scalar() == 0


@pytest.mark.neo4j
@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_bad_requests_are_refused_with_a_readable_reason(graph, clean, anon):
    bad_email = await anon.post("/pilot-requests", json=_body(email="not-an-email"), headers=_ip())
    assert bad_email.status_code == 400 and "work email" in bad_email.json()["detail"]
    blank = await anon.post("/pilot-requests", json=_body(company="   "), headers=_ip())
    assert blank.status_code == 400 and blank.json()["detail"] == "Enter your company."
    assert (await anon.post("/pilot-requests", json=_body(plan="platinum"), headers=_ip())).status_code == 422
    assert (await anon.post("/pilot-requests", json=_body(team_size=0), headers=_ip())).status_code == 422
    cross_site = await anon.post("/pilot-requests", json=_body(), headers={**_ip(), "origin": "https://evil.example"})
    assert cross_site.status_code == 403


@pytest.mark.neo4j
@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_one_network_is_limited_per_hour(graph, clean, anon):
    ip = _ip()
    for _ in range(pilots.PILOT_IP.count):
        assert (await anon.post("/pilot-requests", json=_body(email="limit@example.com"), headers=ip)).status_code == 201
    limited = await anon.post("/pilot-requests", json=_body(email="limit@example.com"), headers=ip)
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0


@pytest.mark.neo4j
@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_only_administrators_list_requests(graph, clean, anon):
    sent = await anon.post("/pilot-requests", json=_body(), headers=_ip())
    assert (await anon.get("/pilot-requests")).status_code == 401
    email = f"user-{uuid.uuid4().hex[:8]}@auth.test"
    member, _ = accounts.register(graph, email, PASSWORD, "Asha", ip="10.91.0.2")
    await anon.post("/auth/login", json={"email": email, "password": PASSWORD}, headers=_ip())
    assert (await anon.get("/pilot-requests")).status_code == 403
    graph.query("MATCH (u:User {id:$id}) SET u.role = 'admin'", {"id": member.id})
    accounts.clear_cache()
    listed = await anon.get("/pilot-requests", params={"limit": 500})
    assert listed.status_code == 200
    row = next(r for r in listed.json()["requests"] if r["reference"] == sent.json()["reference"])
    assert row["company"] == "Acme GCC" and row["plan"] == "transition" and row["created_at_iso"].endswith("Z")
    assert "ip_digest" not in row


@pytest.mark.neo4j
@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_usage_reports_the_plan_and_this_window(graph, clean, anon):
    assert (await anon.get("/auth/usage")).status_code == 401
    email = f"user-{uuid.uuid4().hex[:8]}@auth.test"
    member, _ = accounts.register(graph, email, PASSWORD, "Asha", ip="10.91.0.3")
    await anon.post("/auth/login", json={"email": email, "password": PASSWORD}, headers=_ip())
    limits.hit(graph, limits.ASK, member.id, "x")
    limits.hit(graph, limits.ASK, member.id, "x")
    usage = (await anon.get("/auth/usage")).json()
    assert usage["plan"] == "free" and usage["unlimited"] is False
    assert usage["questions"]["used"] == 2 and usage["questions"]["limit"] == limits.ASK.count
    assert usage["handover_calls"] == {"used": 0, "limit": 10, "window_s": 86_400, "resets_in_s": usage["handover_calls"]["resets_in_s"]}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as guest_client:
        await guest_client.post("/auth/guest", headers=_ip())
        guest = (await guest_client.get("/auth/usage")).json()
    assert guest["plan"] == "guest" and guest["questions"]["limit"] == limits.ASK.count // 4


def test_paid_plans_raise_every_limit_and_keep_the_window():
    team = limits.for_plan(limits.ASK, "team")
    assert team.count == limits.ASK.count * limits.PAID_MULTIPLIER and team.bucket == limits.ASK.bucket
    assert team.window_s == limits.ASK.window_s
    assert limits.for_plan(limits.ASK, "free") == limits.ASK
    assert limits.for_plan(limits.HANDOVER_UPLOAD, "transition").count == 50


@pytest.mark.neo4j
@pytest.mark.real_auth
@pytest.mark.asyncio
async def test_switching_an_account_to_a_paid_plan_lifts_its_allowance(graph, clean, anon, capsys):
    email = f"user-{uuid.uuid4().hex[:8]}@auth.test"
    member, _ = accounts.register(graph, email, PASSWORD, "Asha", ip="10.91.0.4")
    await anon.post("/auth/login", json={"email": email, "password": PASSWORD}, headers=_ip())
    assert (await anon.get("/auth/me")).json()["user"]["plan"] == "free"

    assert cli.main(["plan", email, "transition"]) == 0
    assert "transition" in capsys.readouterr().out
    accounts.clear_cache()
    assert (await anon.get("/auth/me")).json()["user"]["plan"] == "transition"
    usage = (await anon.get("/auth/usage")).json()
    assert usage["plan"] == "transition" and usage["questions"]["limit"] == limits.ASK.count * limits.PAID_MULTIPLIER

    assert cli.main(["plan", email]) == 0 and "transition" in capsys.readouterr().out
    assert cli.main(["plan", "nobody@auth.test", "team"]) == 1
