"""HTTP API through `httpx.ASGITransport`: request validation and the KT 501 without Neo4j, every endpoint with it."""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import HTTPException, Request

from _answer_fixture import Fixture, seed_graph, unseed_people
from untangle.answer import service
from untangle.api import main as api
from untangle.api.auth import enforce_access
from untangle.auth.service import User
from untangle.graph.queries import load_cypher
from untangle.kt.sarvam import BatchPending, SarvamError


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


async def test_kt_ingest_rejects_ambiguous_files(client):
    r = await client.post("/kt/ingest", data={"repo": "o/r"}, files={
        "audio": ("call.wav", b"audio", "audio/wav"),
        "transcript": ("call.json", b"{}", "application/json"),
    })
    assert r.status_code == 400
    assert "exactly one" in r.json()["detail"]


async def test_kt_ingest_rejects_empty_files(client):
    r = await client.post("/kt/ingest", data={"repo": "o/r"}, files={"transcript": ("call.txt", b"")})
    assert r.status_code == 400
    assert "empty" in r.json()["detail"]


async def test_kt_ingest_rejects_files_over_hosting_limit(client):
    r = await client.post("/kt/ingest", data={"repo": "o/r"}, files={"transcript": ("call.txt", b"a" * (4_000_000 + 1))})
    assert r.status_code == 413


async def test_kt_upload_uses_transcript_service(client, monkeypatch):
    calls = []

    def ingest(repo, path, **kwargs):
        calls.append((repo, path.read_text(), kwargs["title"]))
        return {"meeting_id": "mtg:o/r:call", "utterances": 1, "decisions": 0}

    class FakeGraph:
        """The repository is imported and the call is new; owner writes are recorded."""

        def __init__(self):
            self.writes = []

        def read(self, cypher, params=None):
            class Result:
                records = [{"at": 1}] if "Repo" in cypher else []
            return Result()

        def run_named(self, name, params=None, write=False):
            self.writes.append((name, params))

    graph = FakeGraph()
    monkeypatch.setattr(api, "_kt", lambda name: ingest)
    monkeypatch.setattr(service, "get_graph", lambda: graph)
    r = await client.post("/kt/ingest", data={"repo": "o/r", "title": "Handover"},
                          files={"transcript": ("call.txt", b"Sam: We use Neo4j.", "text/plain")})
    assert r.status_code == 200
    assert r.json()["meeting_id"] == "mtg:o/r:call"
    assert calls == [("o/r", "Sam: We use Neo4j.", "Handover")]
    assert graph.writes == [("kt_meeting_owner", {"meeting_id": "mtg:o/r:call", "user_id": "user:test-admin"})]



class PendingGraph:
    """An imported repository with no meetings; pending uploads (`KtUpload`) are kept in memory."""

    def __init__(self):
        self.uploads: dict[str, dict] = {}
        self.writes: list[tuple] = []

    def read(self, cypher, params=None):
        class Result:
            records: list = []
        result = Result()
        if "Repo" in cypher:
            result.records = [{"at": 1}]
        elif "KtUpload" in cypher and params["id"] in self.uploads:
            result.records = [{"p": dict(self.uploads[params["id"]])}]
        return result

    def query(self, cypher, params=None):
        if "CREATE (:KtUpload" in cypher:
            self.uploads[params["id"]] = {k: params[k] for k in ("id", "job_id", "input_name", "repo", "title", "language", "user_id")}
        elif "DETACH DELETE p" in cypher:
            self.uploads.pop(params["id"], None)

    def run_named(self, name, params=None, write=False):
        self.writes.append((name, params))


async def test_long_recordings_keep_transcribing_after_the_first_request(client, monkeypatch):
    graph, waits, polls = PendingGraph(), [], {"n": 0}

    def ingest_audio(repo, title, path, **kwargs):
        waits.append(kwargs["batch_timeout"])
        raise BatchPending("job-9", "upload.mp3", "running")

    def resume_audio(repo, title, job_id, input_name, **kwargs):
        assert (repo, title, job_id, input_name) == ("o/r", "Long call", "job-9", "upload.mp3")
        assert kwargs["batch_timeout"] == api._RESUME_WAIT_SECONDS
        polls["n"] += 1
        if polls["n"] == 1:
            raise BatchPending(job_id, input_name, "running")
        return {"meeting_id": "mtg:o/r:long", "utterances": 3, "decisions": 1}

    functions = {"ingest_audio": ingest_audio, "resume_audio": resume_audio}
    monkeypatch.setattr(api, "_kt", lambda name: functions[name])
    monkeypatch.setattr(service, "get_graph", lambda: graph)
    r = await client.post("/kt/ingest", data={"repo": "o/r", "title": "Long call"}, files={"audio": ("call.mp3", b"ID3audio", "audio/mpeg")})
    assert r.status_code == 202
    assert r.json()["status"] == "transcribing"
    upload_id = r.json()["upload_id"]
    assert 0 < waits[0] <= api._TRANSCRIBE_WAIT_SECONDS
    assert graph.uploads[upload_id]["user_id"] == "user:test-admin"

    r = await client.post(f"/kt/ingest/{upload_id}/resume")
    assert r.status_code == 202 and r.json()["upload_id"] == upload_id
    r = await client.post(f"/kt/ingest/{upload_id}/resume")
    assert r.status_code == 200 and r.json()["meeting_id"] == "mtg:o/r:long"
    assert graph.writes == [("kt_meeting_owner", {"meeting_id": "mtg:o/r:long", "user_id": "user:test-admin"})]
    assert graph.uploads == {}
    assert (await client.post(f"/kt/ingest/{upload_id}/resume")).status_code == 404


async def test_a_failed_transcription_is_reported_and_forgotten(client, monkeypatch):
    graph = PendingGraph()
    graph.uploads["u1"] = {"id": "u1", "job_id": "job-5", "input_name": "upload.mp3", "repo": "o/r", "title": "Call", "language": None, "user_id": "user:test-admin"}

    def resume_audio(*args, **kwargs):
        raise SarvamError("batch job job-5 Failed: unsupported codec")

    monkeypatch.setattr(api, "_kt", lambda name: resume_audio)
    monkeypatch.setattr(service, "get_graph", lambda: graph)
    r = await client.post("/kt/ingest/u1/resume")
    assert r.status_code == 502
    assert graph.uploads == {}


async def test_only_the_uploader_can_collect_a_pending_recording(client, monkeypatch):
    graph = PendingGraph()
    graph.uploads["u2"] = {"id": "u2", "job_id": "job-6", "input_name": "upload.mp3", "repo": "o/r", "title": "Call", "language": None, "user_id": "user:someone-else"}
    member = User(id="user:member", email="member@untangle.test", name="Member", role="member", created_at=0)

    def as_member(req: Request) -> None:
        req.state.user = member

    monkeypatch.setattr(api, "_kt", lambda name: pytest.fail("another person's upload must not be resumed"))
    monkeypatch.setattr(service, "get_graph", lambda: graph)
    api.app.dependency_overrides[enforce_access] = as_member
    r = await client.post("/kt/ingest/u2/resume")
    assert r.status_code == 404
    assert "u2" in graph.uploads


def test_meeting_reads_return_the_uploader_for_delete_permissions():
    for name in ("kt_meetings", "kt_meeting_detail"):
        assert "m.uploaded_by AS uploaded_by" in load_cypher(name)


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


async def test_health_reports_failed_embeddings_without_crashing(client, monkeypatch):
    def unavailable():
        raise RuntimeError("read-only model cache")

    monkeypatch.setattr(service, "make_embedder", unavailable)
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"
    assert r.json()["optional_backends"]["embeddings"]["available"] is False


def test_kt_delegation_answers_501_when_the_function_is_missing():
    with pytest.raises(HTTPException) as exc:
        api._kt("definitely_not_a_kt_function")
    assert exc.value.status_code == 501
    assert "untangle.kt.service" in exc.value.detail


async def test_openapi_lists_every_contract_endpoint(client):
    # The schema is not published in production (UNTANGLE_API_DOCS is off), but every contract route exists.
    assert (await client.get("/openapi.json")).status_code == 404
    assert (await client.get("/docs")).status_code == 404
    paths = api.app.openapi()["paths"]
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
    assert h["ok"] is True and h["graph"]["ok"] and h["llm"]["backend"] == "fake" and h["embed"]["dim"] == 384
    # Public health never names the database host, versions or the hosted model.
    assert "uri" not in h["neo4j"] and "version" not in h["neo4j"] and "model" not in h["llm"]
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


async def test_a_link_cut_short_opens_the_one_record_it_starts_with(client, monkeypatch):
    """Crawlers, chat apps and mail clients cut long URLs; a unique prefix still opens the record."""
    full = "cfg:knadh/listmonk:config.toml.sample::smtp.my0.max_msg_retries"
    asked = []

    class PrefixGraph:
        def read(self, cypher, params=None):
            class Result:
                records: list = []
            result = Result()
            asked.append(cypher)
            if "STARTS WITH" in cypher and full.startswith(params["prefix"]):
                result.records = [{"id": full}]
            return result

    def entity(entity_id, **kwargs):
        if entity_id != full:
            raise service.NotFound(f"no entity {entity_id!r}")
        return {"entity": {"id": full, "label": "ConfigKey"}, "decisions": [], "people": [], "recent_commits": []}

    monkeypatch.setattr(service, "get_graph", lambda: PrefixGraph())
    monkeypatch.setattr(service, "entity", entity)
    r = await client.get(f"/entities/{full[:60]}")
    assert r.status_code == 200 and r.json()["entity"]["id"] == full
    assert "MATCH (n:ConfigKey)" in asked[0]
    # Too short, or of an unknown kind: never guessed.
    assert (await client.get("/entities/cfg:knadh/lis")).status_code == 404
    assert (await client.get("/entities/unknown:knadh/listmonk:config.toml.sample::smtp")).status_code == 404


def test_cut_short_ids_resolve_only_when_one_record_matches():
    class TwoMatches:
        def read(self, cypher, params=None):
            class Result:
                records = [{"id": "dec:o/r:config_value:aaaa1111"}, {"id": "dec:o/r:config_value:aaaa2222"}]
            return Result()

    assert api._complete_id("dec:o/r:config_value:aaaa", TwoMatches()) is None
