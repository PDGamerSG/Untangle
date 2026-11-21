"""The MCP endpoint: protocol handling without a database, then tokens and agent memory against Neo4j."""

from __future__ import annotations

import uuid

import httpx
import pytest

from _answer_fixture import seed_graph, unseed_people
from untangle import mcp_server
from untangle.api import main as api
from untangle.auth import tokens
from untangle.auth.service import User

USER = User(id="user:mcp-test", email="mcp@auth.test", name="MCP tester", role="member", created_at=0)


def _rpc(method: str, params: dict | None = None, id_: int | None = 1) -> dict:
    message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if id_ is not None:
        message["id"] = id_
    return message


def _no_charge(kind: str) -> None:
    return None


def test_initialize_negotiates_the_protocol_version():
    reply = mcp_server.handle(_rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}), USER, charge=_no_charge)
    result = reply["result"]
    assert result["protocolVersion"] == "2025-06-18"
    assert result["capabilities"] == {"tools": {"listChanged": False}}
    assert result["serverInfo"]["name"] == "untangle" and "remember_decision" in result["instructions"]
    unknown = mcp_server.handle(_rpc("initialize", {"protocolVersion": "1999-01-01"}), USER, charge=_no_charge)
    assert unknown["result"]["protocolVersion"] == mcp_server.PROTOCOL_VERSIONS[0]


def test_tools_are_listed_with_schemas_and_annotations():
    tools = {t["name"]: t for t in mcp_server.handle(_rpc("tools/list"), USER, charge=_no_charge)["result"]["tools"]}
    assert set(tools) == {"list_repositories", "ask_why", "list_decisions", "decision_timeline", "who_to_ask",
                          "search_repository", "check_change", "repository_briefing", "remember_decision", "recall_agent_notes"}
    assert tools["check_change"]["inputSchema"]["required"] == ["repo"]
    assert tools["check_change"]["annotations"]["openWorldHint"] is True  # it may look up public advisories
    assert tools["ask_why"]["inputSchema"]["required"] == ["repo", "question"]
    assert tools["remember_decision"]["annotations"]["readOnlyHint"] is False
    assert all(t["annotations"]["readOnlyHint"] for name, t in tools.items() if name != "remember_decision")


def test_protocol_errors_and_notifications():
    assert mcp_server.handle(_rpc("notifications/initialized", id_=None), USER, charge=_no_charge) is None
    assert mcp_server.handle([_rpc("ping")], USER, charge=_no_charge)["error"]["code"] == -32600
    assert mcp_server.handle({"method": "ping", "id": 1}, USER, charge=_no_charge)["error"]["code"] == -32600
    assert mcp_server.handle(_rpc("resources/list"), USER, charge=_no_charge)["error"]["code"] == -32601
    assert mcp_server.handle(_rpc("tools/call", {"name": "drop_database"}), USER, charge=_no_charge)["error"]["code"] == -32602
    assert mcp_server.handle(_rpc("ping"), USER, charge=_no_charge)["result"] == {}


def test_tool_input_problems_are_reported_to_the_agent(monkeypatch):
    monkeypatch.setattr(mcp_server.service, "repos", lambda: [])
    reply = mcp_server.handle(_rpc("tools/call", {"name": "ask_why", "arguments": {"question": "why?"}}), USER, charge=_no_charge)
    assert reply["result"]["isError"] is True and "repo is required" in reply["result"]["content"][0]["text"]
    reply = mcp_server.handle(_rpc("tools/call", {"name": "ask_why", "arguments": {"repo": "o/r", "question": "why?"}}), USER, charge=_no_charge)
    assert "not indexed" in reply["result"]["content"][0]["text"]


def test_limits_become_tool_errors():
    def refuse(kind: str) -> None:
        raise mcp_server.ToolError("This account reached its limit for this tool.")

    reply = mcp_server.handle(_rpc("tools/call", {"name": "list_repositories", "arguments": {}}), USER, charge=refuse)
    assert reply["result"]["isError"] is True


@pytest.mark.real_auth
async def test_the_endpoint_needs_a_token():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as c:
        missing = await c.post("/mcp", json=_rpc("ping"))
        assert missing.status_code == 401 and missing.headers["www-authenticate"].startswith("Bearer")
        assert (await c.post("/mcp", json=_rpc("ping"), headers={"Authorization": "Bearer utg_not-a-real-token"})).status_code == 401
        # Tokens only open the agent endpoint, never the browser API.
        assert (await c.get("/repos", headers={"Authorization": "Bearer utg_not-a-real-token"})).status_code == 401


# -- with Neo4j -------------------------------------------------------------------------------------------------------


@pytest.mark.neo4j
@pytest.mark.real_auth
async def test_agents_read_and_write_decision_memory(graph):
    repo = f"test/mcp{uuid.uuid4().hex[:6]}"
    fx = seed_graph(graph, repo, suffix=uuid.uuid4().hex[:6])
    tokens.clear_cache()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as c:
            email = f"agent-{uuid.uuid4().hex[:8]}@auth.test"
            r = await c.post("/auth/register", json={"email": email, "password": "correct horse battery staple"}, headers={"x-real-ip": "10.9.9.9"})
            assert r.status_code == 201
            created = await c.post("/auth/tokens", json={"name": "Claude Code laptop"})
            assert created.status_code == 201
            token = created.json()["token"]
            assert token.startswith("utg_")
            listed = (await c.get("/auth/tokens")).json()["tokens"]
            assert listed[0]["name"] == "Claude Code laptop" and "token" not in listed[0]
            assert not graph.read("MATCH (k:ApiToken {id: $t}) RETURN k", {"t": token}).records  # only the hash is stored
            c.cookies.clear()

            agent = {"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream"}

            async def call(name: str, arguments: dict) -> dict:
                reply = await c.post("/mcp", json=_rpc("tools/call", {"name": name, "arguments": arguments}), headers=agent)
                assert reply.status_code == 200, reply.text
                return reply.json()["result"]

            init = await c.post("/mcp", json=_rpc("initialize", {"protocolVersion": "2025-06-18"}), headers=agent)
            assert init.json()["result"]["serverInfo"]["name"] == "untangle"
            assert (await c.post("/mcp", json=_rpc("notifications/initialized", id_=None), headers=agent)).status_code == 202

            repos = await call("list_repositories", {})
            assert repo in {r["repo"] for r in repos["structuredContent"]["repositories"]}

            decisions = await call("list_decisions", {"repo": repo, "subject": "app.concurrency"})
            assert not decisions["isError"] and decisions["structuredContent"]["decisions"]

            first = await call("remember_decision", {"repo": repo, "subject": "config.toml", "topic": "Retry policy",
                                                     "decision": "Keep retries at three until the mail provider fixes duplicate sends.",
                                                     "rationale": "Higher values caused duplicate deliveries.", "source_url": "https://github.com/o/r/pull/1"})
            assert not first["isError"], first
            second = await call("remember_decision", {"repo": repo, "subject": "config.toml", "topic": "retry policy",
                                                      "decision": "Retries may go to five now that the provider deduplicates."})
            assert second["structuredContent"]["supersedes"] == [first["structuredContent"]["id"]]

            notes = await call("recall_agent_notes", {"repo": repo})
            statuses = {n["id"]: n["status"] for n in notes["structuredContent"]["notes"]}
            assert statuses[first["structuredContent"]["id"]] == "superseded" and statuses[second["structuredContent"]["id"]] == "active"
            stored = graph.read("MATCH (d:Decision {id: $id})-[:ABOUT]->(f:File) RETURN d.kind AS kind, d.recorded_by_name AS who, f.path AS path",
                                {"id": second["structuredContent"]["id"]}).records
            assert stored == [{"kind": "agent", "who": email.split("@")[0], "path": "config.toml"}]

            bad = await call("remember_decision", {"repo": repo, "subject": "no/such/file.py", "decision": "Something was decided here."})
            assert bad["isError"] and "search_repository" in bad["content"][0]["text"]
            unsafe = await call("remember_decision", {"repo": repo, "subject": "config.toml", "decision": "A decision with a bad link.", "source_url": "javascript:alert(1)"})
            assert unsafe["isError"]

            answer = await call("ask_why", {"repo": repo, "question": "why is app.concurrency set the way it is?"})
            assert not answer["isError"] and answer["structuredContent"]["citations"]
            # Repository evidence still leads the answer; the agent note does not replace it.
            assert "dec:" in answer["content"][0]["text"] and "agent" not in answer["structuredContent"]["answer"].lower()

            people = await call("who_to_ask", {"repo": repo, "subject": "config.toml"})
            assert not people["isError"]

            # Revoking a token stops it at once.
            short_id = listed[0]["id"]
            c.cookies.clear()
            login = await c.post("/auth/login", json={"email": email, "password": "correct horse battery staple"}, headers={"x-real-ip": "10.9.9.8"})
            assert login.status_code == 200
            assert (await c.delete(f"/auth/tokens/{short_id}")).status_code == 204
            c.cookies.clear()
            assert (await c.post("/mcp", json=_rpc("ping"), headers=agent)).status_code == 401
    finally:
        graph.wipe_repo(repo)
        unseed_people(graph, fx)
        graph.query("MATCH (u:User) WHERE u.email ENDS WITH '@auth.test' OPTIONAL MATCH (u)-[:HAS_SESSION|HAS_TOKEN]->(x) DETACH DELETE x, u")
        tokens.clear_cache()
