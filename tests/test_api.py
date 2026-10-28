"""HTTP API through `httpx.ASGITransport`: request validation and the KT 501 without Neo4j, every endpoint with it."""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import HTTPException

from _answer_fixture import Fixture, seed_graph, unseed_people
from untangle.answer import service
from untangle.api import main as api


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as c:
        yield c


async def test_ask_rejects_bad_bodies(client):
    r = await client.post("/ask", json={"question": "why?", "repo": "o/r", "mode": "magic"})
    assert r.status_code == 422
    r = await client.post("/ask", json={"repo": "o/r"})
    assert r.status_code == 422


async def test_kt_ingest_requires_a_file(client):
    r = await client.post("/kt/ingest", data={"repo": "o/r"})
    assert r.status_code == 400
    assert "audio" in r.json()["detail"]


async def test_request_id_is_echoed_and_added_to_errors(client):
    r = await client.get("/decisions/missing")
    request_id = r.headers.get("x-request-id")
    assert request_id
    assert r.json()["request_id"] == request_id


async def test_health_exposes_process_and_graph_status(client):
    payload = (await client.get("/health")).json()
    assert payload["status"] in {"ok", "degraded"}
    assert "graph" in payload and "ok" in payload["graph"]
    assert "optional_backends" in payload
    assert "sarvam" in payload["optional_backends"]


def test_kt_delegation_answers_501_when_the_function_is_missing():
    with pytest.raises(HTTPException) as exc:
        api._kt("definitely_not_a_kt_function")
    assert exc.value.status_code == 501
    assert "untangle.kt.service" in exc.value.detail


async def test_openapi_lists_every_contract_endpoint(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    for path in ("/health", "/repos", "/ask", "/decisions/{decision_id}", "/entities/{entity_id}", "/search", "/timeline", "/pulse", "/meetings", "/meetings/{meeting_id}", "/kt/ingest", "/stats"):
        assert path in paths, path


# -- with Neo4j -------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def seeded_api(graph):
    suffix = uuid.uuid4().hex[:6]
    repo = f"test/api{suffix}"
    fx = seed_graph(graph, repo, suffix=suffix)
    yield fx
    unseed_people(graph, fx)
    graph.wipe_repo(repo)


@pytest.mark.neo4j
async def test_health_and_repos(client, graph, seeded_api: Fixture):
    h = (await client.get("/health")).json()
    assert h["ok"] is True and h["neo4j"]["version"] and h["llm"]["backend"] == "fake" and h["embed"]["dim"] == 384
    repos = (await client.get("/repos")).json()
    mine = next(r for r in repos if r["full_name"] == seeded_api.repo)
    assert mine["counts"]["decisions"] == 2 and mine["head_sha"]


@pytest.mark.neo4j
async def test_ask_matches_the_service(client, graph, seeded_api: Fixture):
    body = {"question": "why is app.concurrency 10 in config.toml?", "repo": seeded_api.repo, "mode": "both"}
    r = await client.post("/ask", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    direct = service.ask(body["question"], body["repo"], mode="both", graph=graph)
    assert data["answer"] == direct.answer
    assert data["refused"] is False and data["confidence"]["label"] == direct.confidence.label
    assert data["supersession"][0]["newer"] == seeded_api.dec_new
    assert data["why"]["subgraph"]["edges"][0].keys() >= {"from", "to", "type"}
    assert data["baseline"]["note"].startswith("vector-only")
    assert set(data) >= {"question", "repo", "mode", "answer", "refused", "confidence", "evidence_chain", "supersession", "citations", "entities", "why", "baseline"}
    assert r.headers["x-untangle-ms"]
    at = await client.post("/ask", json={"question": "what was app.concurrency?", "repo": seeded_api.repo, "at": "2022-05-01"})
    assert at.json()["answer"].startswith("On 1 May 2022")
    bad = await client.post("/ask", json={"question": "what was app.concurrency?", "repo": seeded_api.repo, "at": "yesterday"})
    assert bad.status_code == 400 and "error" in bad.json()


@pytest.mark.neo4j
async def test_decisions_entities_search_timeline_stats(client, graph, seeded_api: Fixture):
    wp = (await client.get(f"/decisions/{seeded_api.dec_new}")).json()
    assert wp["decision"]["id"] == seeded_api.dec_new and wp["older"][0]["id"] == seeded_api.dec_old
    assert (await client.get("/decisions/dec:nope")).status_code == 404

    ent = (await client.get(f"/entities/{seeded_api.cfg}")).json()
    assert ent["entity"]["key"] == "app.concurrency" and len(ent["decisions"]) == 2 and ent["people"][0]["name"] == "Kailash Nadh"
    assert (await client.get("/entities/file:nope")).status_code == 404

    found = (await client.get("/search", params={"repo": seeded_api.repo, "q": "config.toml"})).json()
    assert found["entities"][0]["id"] == seeded_api.file

    tl = (await client.get("/timeline", params={"repo": seeded_api.repo, "at": "2022-05-01"})).json()
    assert tl["at_iso"] == "2022-05-01T00:00:00Z" and tl["active"][0]["id"] == seeded_api.dec_old

    stats = (await client.get("/stats", params={"repo": seeded_api.repo})).json()
    assert stats["labels"]["Decision"] == 2 and stats["relationship_types"]["SUPERSEDES"] == 1


@pytest.mark.neo4j
async def test_meetings_answer_501_or_delegate(client, graph, seeded_api: Fixture):
    r = await client.get("/meetings", params={"repo": seeded_api.repo})
    assert r.status_code in (200, 501)
