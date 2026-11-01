"""Public onboarding: validation, durable queue ownership, recovery and actual ingestion."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
import respx

from untangle.answer import service as answers
from untangle.api.main import app
from untangle.config import settings


@pytest.fixture
def imports_enabled(monkeypatch):
    monkeypatch.setenv("REPO_IMPORTS_ENABLED", "true")
    settings.cache_clear()
    yield
    settings.cache_clear()


@pytest.fixture
def metadata(test_repo):
    return {"full_name": test_repo, "private": False, "size": 50, "default_branch": "main", "description": "Example repository"}


@pytest.mark.asyncio
async def test_onboarding_rejects_non_github_urls_before_fetching(imports_enabled):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/repository-imports", json={"repository": "http://127.0.0.1/private"})
    assert response.status_code == 400
    assert "GitHub" in response.json()["error"]


@pytest.mark.parametrize("value,want", [
    (" PDGamerSG/Untangle ", "PDGamerSG/Untangle"),
    ("https://github.com/PDGamerSG/Untangle.git/", "PDGamerSG/Untangle"),
    ("https://github.com/owner/repo", "owner/repo"),
])
def test_repository_names_are_normalized(value, want):
    from untangle.repositories.service import normalize_repository
    assert normalize_repository(value) == want


@pytest.mark.parametrize("value", [
    "../repo", "owner/..", "-owner/repo", "owner/repo/extra", "git@github.com:o/r", "file:///tmp/repo",
    "https://github.com.evil.test/o/r", "https://user:secret@github.com/o/r", "https://github.com:8080/o/r",
    "https://github.com/o/r?token=secret", "https://github.com/o/%2e%2e", "https://evil.test/github.com/o/r",
])
def test_repository_names_cannot_escape_github_or_cache(value):
    from untangle.repositories.service import ImportProblem, normalize_repository
    with pytest.raises(ImportProblem):
        normalize_repository(value)


def test_import_estimate_reports_elapsed_and_overdue_without_false_completion():
    from untangle.repositories.jobs import _public

    row = {"id": "job", "repo": "o/r", "status": "running", "stage": "git", "progress": 5,
           "created_at": 1000, "started_at": 1000, "metadata": '{"size": 50}'}
    early = _public(row, now=31_000)["estimate"]
    assert early["elapsed_seconds"] == 30
    assert 0 < early["remaining_min_seconds"] < early["remaining_max_seconds"]
    assert not early["overdue"]
    late = _public(row, now=3_601_000)["estimate"]
    assert late["overdue"] and late["remaining_max_seconds"] is None
    done = _public({**row, "status": "complete", "finished_at": 61_000}, now=120_000)["estimate"]
    assert done["elapsed_seconds"] == 60 and done["remaining_max_seconds"] == 0


@respx.mock
@pytest.mark.parametrize("body,status", [({"private": True}, 400), ({"disabled": True}, 400), ({"size": 100_001}, 413)])
def test_private_disabled_and_large_repositories_are_rejected(body, status):
    from untangle.repositories.service import ImportProblem, fetch_public_repository
    respx.get("https://api.github.com/repos/owner/repo").respond(200, json={"full_name": "owner/repo", "private": False, "size": 10, **body})
    with pytest.raises(ImportProblem) as error:
        fetch_public_repository("owner/repo")
    assert error.value.status == status


@respx.mock
@pytest.mark.parametrize("status,want", [(404, 404), (403, 503), (429, 503), (500, 503)])
def test_github_failures_have_actionable_status(status, want):
    from untangle.repositories.service import ImportProblem, fetch_public_repository
    respx.get("https://api.github.com/repos/owner/repo").respond(status)
    with pytest.raises(ImportProblem) as error:
        fetch_public_repository("owner/repo")
    assert error.value.status == want


@pytest.mark.neo4j
def test_duplicate_submissions_and_worker_claims_are_atomic(graph, metadata):
    from untangle.repositories.jobs import claim_next, enqueue
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = list(pool.map(lambda _: enqueue(graph, metadata), range(5)))
    assert len({job["id"] for job in jobs}) == 1
    with ThreadPoolExecutor(max_workers=5) as pool:
        claims = list(pool.map(lambda _: claim_next(graph), range(5)))
    claimed = [claim for claim in claims if claim]
    assert len(claimed) == 1
    assert claimed[0]["id"] == jobs[0]["id"] and claimed[0]["status"] == "running"


@pytest.mark.neo4j
def test_expired_worker_cannot_complete_job_and_retry_creates_new_job(graph, metadata):
    from untangle.repositories.jobs import claim_next, complete, enqueue, expire_stalled, get_job
    job = enqueue(graph, metadata, now=1_000_000)
    claim = claim_next(graph, now=1_000_001)
    expire_stalled(graph, now=10_000_000)
    assert get_job(graph, job["id"])["status"] == "failed"
    assert not complete(graph, job["id"], claim["lease_token"], {"commits": 2}, [])
    retry = enqueue(graph, metadata, now=10_000_001)
    assert retry["id"] != job["id"] and retry["status"] == "queued"


@pytest.mark.neo4j
def test_queue_capacity_blocks_new_work_but_allows_duplicate_status(graph, metadata):
    from untangle.repositories.jobs import enqueue
    from untangle.repositories.service import ImportProblem
    try:
        for i in range(6):
            enqueue(graph, {**metadata, "full_name": metadata["full_name"] + f"-{i}"})
        duplicate = enqueue(graph, {**metadata, "full_name": metadata["full_name"] + "-0"})
        assert duplicate["status"] == "queued"
        with pytest.raises(ImportProblem) as error:
            enqueue(graph, {**metadata, "full_name": metadata["full_name"] + "-extra"})
        assert error.value.status == 429
    finally:
        graph.query("MATCH (j:RepositoryImport) WHERE j.repo STARTS WITH $prefix DETACH DELETE j", {"prefix": metadata["full_name"] + "-"})


@pytest.mark.neo4j
def test_import_worker_populates_all_repository_workflows(graph, metadata, tmp_path):
    from ingest_fixture import build_repo
    from untangle.ingest.pipeline import ingest_repo
    from untangle.repositories.jobs import enqueue, get_job
    from untangle.repositories.service import overview
    from untangle.repositories.worker import process_one
    from untangle.repository_map.service import repository_map

    path = tmp_path / "repo"
    build_repo(path)
    job = enqueue(graph, metadata)

    def ingest(repo, **kwargs):
        kwargs.pop("cache_dir")
        return ingest_repo(repo, **{**kwargs, "repo_path": path, "github": False})

    assert process_one(graph, ingester=ingest, validator=lambda repo: metadata)
    finished = get_job(graph, job["id"])
    assert finished["status"] == "complete" and finished["summary"]["commits"] == 6
    assert "lease_token" not in finished
    inventory = overview(metadata["full_name"], graph)
    assert inventory["counts"]["decisions"] == 12
    assert inventory["counts"]["people"] == 1 and inventory["counts"]["dependencies"] == 1
    assert inventory["counts"]["files"] == 9 and inventory["counts"]["current_files"] == 8
    # Contributors include people who only participate in issues or PRs, counted once.
    graph.query("""CREATE (p:Person {id:$repo+'-reviewer'})
      CREATE (i:Issue {id:$repo+'-issue',repo:$repo})
      CREATE (pr:PullRequest {id:$repo+'-pr',repo:$repo})
      CREATE (p)-[:AUTHORED]->(i) CREATE (p)-[:AUTHORED]->(pr)""", {"repo": metadata["full_name"]})
    assert overview(metadata["full_name"], graph)["counts"]["people"] == 2
    assert inventory["dependencies"][0]["name"] == "github.com/lib/pq"
    assert inventory["suggested_questions"]
    assert repository_map(metadata["full_name"], graph)["total_commits"] == 6
    answer = answers.ask("what is app.retry_limit in config/app.yaml?", metadata["full_name"], graph=graph)
    assert not answer.refused and answer.citations


@pytest.mark.neo4j
def test_worker_failure_is_persisted_without_leaking_exception_secrets(graph, metadata):
    from untangle.repositories.jobs import enqueue, get_job
    from untangle.repositories.worker import process_one
    job = enqueue(graph, metadata)

    def broken(repo, **kwargs):
        raise RuntimeError("secret-should-not-be-public")

    process_one(graph, ingester=broken, validator=lambda repo: metadata)
    result = get_job(graph, job["id"])
    assert result["status"] == "failed"
    assert "secret-should-not-be-public" not in str(result)


@pytest.mark.neo4j
def test_completed_job_coalesces_until_refresh_interval_and_inventory_is_scoped(graph, metadata):
    from untangle.repositories.jobs import claim_next, complete, enqueue
    from untangle.repositories.models import ImportProblem
    from untangle.repositories.service import overview
    job = enqueue(graph, metadata)
    claim = claim_next(graph)
    assert complete(graph, job["id"], claim["lease_token"], {"commits": 4}, [])
    assert enqueue(graph, metadata)["id"] == job["id"]
    graph.query("MATCH (j:RepositoryImport {id:$id}) SET j.finished_at=0", {"id": job["id"]})
    assert enqueue(graph, metadata)["id"] != job["id"]
    with pytest.raises(ImportProblem) as error:
        overview(metadata["full_name"] + "-not-ingested", graph)
    assert error.value.status == 404


@pytest.mark.neo4j
def test_daily_quota_counts_completed_jobs_but_recent_duplicate_is_reusable(graph, metadata):
    from untangle.repositories.jobs import clock_ms, enqueue
    from untangle.repositories.models import ImportProblem
    prefix = metadata["full_name"] + "-quota-"
    now = clock_ms()
    graph.query("UNWIND range(1,20) AS i CREATE (j:RepositoryImport {id:$prefix+toString(i),repo:$prefix+toString(i),status:'complete',created_at:$now})", {"prefix": prefix, "now": now})
    try:
        with pytest.raises(ImportProblem) as error:
            enqueue(graph, metadata)
        assert error.value.status == 429
    finally:
        graph.query("MATCH (j:RepositoryImport) WHERE j.repo STARTS WITH $prefix DETACH DELETE j", {"prefix": prefix})


@pytest.mark.asyncio
@pytest.mark.neo4j
@respx.mock
async def test_import_http_contract_survives_page_reload(graph, metadata, imports_enabled, monkeypatch):
    monkeypatch.setattr(answers, "get_graph", lambda: graph)
    respx.get(f"https://api.github.com/repos/{metadata['full_name']}").respond(200, json=metadata)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/repository-imports", json={"repository": metadata["full_name"]})
        assert first.status_code == 202
        job = first.json()
        again = await client.get(f"/repository-imports/{job['id']}")
        assert again.status_code == 200 and again.json()["repo"] == metadata["full_name"]
        listing = (await client.get("/repository-imports")).json()
        assert listing["enabled"] and any(j["id"] == job["id"] for j in listing["jobs"])
        assert (await client.get("/repository-imports/nonexistent")).status_code == 404
