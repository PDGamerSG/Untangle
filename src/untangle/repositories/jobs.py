"""Neo4j queue. A control-node write serializes admission and claims across API/worker instances."""

from __future__ import annotations

import json
import time
import uuid

from untangle.answer.text import iso
from untangle.graph.db import Graph
from untangle.repositories.models import (
    LEASE_TIMEOUT_MS,
    LIMITS,
    MAX_PENDING,
    QUEUE_TIMEOUT_MS,
    REFRESH_INTERVAL_MS,
    ImportProblem,
)


def clock_ms() -> int:
    return int(time.time() * 1000)


def _public(row: dict, *, now: int | None = None) -> dict:
    now = clock_ms() if now is None else now
    elapsed = max(0, ((row.get("finished_at") or now) - (row.get("created_at") or now)) // 1000)
    size = json.loads(row.get("metadata") or "{}").get("size", 0)
    # Planning ranges, not a countdown derived from stage percentages:
    # GitHub volume, worker scheduling and embedding cold starts vary widely.
    low, high = (120, 600) if size < 5000 else (300, 1200)
    if row["status"] == "queued":
        low, high = low + 60, high + 600
        age = elapsed
    else:
        age = max(0, (now - (row.get("started_at") or now)) // 1000)
    terminal = row["status"] in ("complete", "failed")
    overdue = not terminal and age >= high
    return {
        "id": row["id"], "repo": row["repo"], "url": f"https://github.com/{row['repo']}",
        "status": row["status"], "stage": row["stage"], "progress": row.get("progress", 0),
        "message": row.get("message", ""), "error": row.get("error"), "warnings": row.get("warnings") or [],
        "summary": json.loads(row["summary"]) if row.get("summary") else None,
        "estimate": {"elapsed_seconds": elapsed, "remaining_min_seconds": 0 if terminal else max(30, low - age),
                     "remaining_max_seconds": 0 if terminal else None if overdue else max(60, high - age), "overdue": overdue},
        **{f"{key}_iso": iso(row.get(key)) for key in ("created_at", "updated_at", "started_at", "finished_at")},
    }


def _lock(tx):
    tx.run("MERGE (c:ImportControl {id: 'repositories'}) SET c.version = coalesce(c.version, 0) + 1").consume()


def enqueue(graph: Graph, metadata: dict, *, now: int | None = None) -> dict:
    now = clock_ms() if now is None else now
    repo, job_id = metadata["full_name"], uuid.uuid4().hex

    def work(tx):
        _lock(tx)
        previous = tx.run("MATCH (j:RepositoryImport {repo_key: $key}) RETURN properties(j) AS job ORDER BY j.created_at DESC LIMIT 1", key=repo.lower()).single()
        if previous:
            job = dict(previous["job"])
            if job["status"] in ("queued", "running") or (job["status"] == "complete" and job.get("finished_at", 0) > now - REFRESH_INTERVAL_MS):
                return _public(job)
        counts = tx.run("MATCH (j:RepositoryImport) RETURN count(CASE WHEN j.status IN ['queued','running'] THEN 1 END) AS active, count(CASE WHEN j.created_at >= $day THEN 1 END) AS today", day=now - 86400000).single()
        if counts["active"] >= MAX_PENDING:
            raise ImportProblem(429, "The shared import queue is full. Please try again after an import finishes.")
        if counts["today"] >= LIMITS["imports_per_day"]:
            raise ImportProblem(429, "The shared daily import limit has been reached. Please try again tomorrow.")
        row = {"id": job_id, "repo": repo, "repo_key": repo.lower(), "status": "queued", "stage": "queued", "progress": 0,
               "message": "Waiting for the repository worker. You can leave this page and return later.",
               "metadata": json.dumps(metadata), "created_at": now, "updated_at": now, "warnings": []}
        tx.run("CREATE (j:RepositoryImport) SET j = $row", row=row).consume()
        return _public(row)
    return graph.transaction(work)


def get_job(graph: Graph, job_id: str) -> dict:
    rows = graph.read("MATCH (j:RepositoryImport {id: $id}) RETURN properties(j) AS job", {"id": job_id}).records
    if not rows:
        raise ImportProblem(404, "This repository import was not found.")
    return _public(rows[0]["job"])


def list_jobs(graph: Graph) -> list[dict]:
    rows = graph.read("MATCH (j:RepositoryImport) RETURN properties(j) AS job ORDER BY j.created_at DESC LIMIT 30").records
    return [_public(row["job"]) for row in rows]


def expire_stalled(graph: Graph, *, now: int | None = None) -> None:
    now = clock_ms() if now is None else now
    graph.query("""MATCH (j:RepositoryImport)
      WHERE (j.status = 'running' AND j.updated_at < $lease) OR (j.status = 'queued' AND j.created_at < $queue)
      SET j.status = 'failed', j.stage = 'failed', j.error = 'The import worker stopped or did not start in time. Add this repository again to retry.',
          j.message = 'Import interrupted. You can retry.', j.updated_at = $now, j.finished_at = $now
      REMOVE j.lease_token""", {"now": now, "lease": now - LEASE_TIMEOUT_MS, "queue": now - QUEUE_TIMEOUT_MS})


def claim_next(graph: Graph, *, now: int | None = None) -> dict | None:
    now = clock_ms() if now is None else now
    token = uuid.uuid4().hex

    def work(tx):
        _lock(tx)
        # Only one active ingestion: shared people/file writes and CPU embeddings stay bounded.
        if tx.run("MATCH (j:RepositoryImport {status:'running'}) RETURN j.id LIMIT 1").single():
            return None
        row = tx.run("""MATCH (j:RepositoryImport {status:'queued'}) WITH j ORDER BY j.created_at LIMIT 1
          SET j.status='running', j.stage='git', j.progress=5, j.started_at=$now, j.updated_at=$now,
              j.lease_token=$token, j.message='Reading repository metadata and Git history.'
          RETURN properties(j) AS job""", now=now, token=token).single()
        return dict(row["job"]) if row else None
    return graph.transaction(work)


def worker_seen(graph: Graph) -> None:
    graph.query("MERGE (c:ImportControl {id:'repositories'}) SET c.last_seen_at=$now", {"now": clock_ms()})


def update_progress(graph: Graph, job_id: str, token: str, stage: str, progress: int, message: str) -> bool:
    return bool(graph.query("""MATCH (j:RepositoryImport {id:$id,status:'running',lease_token:$token})
      SET j.updated_at=$now, j.stage=$stage, j.progress=$progress, j.message=$message RETURN j.id""",
      {"id": job_id, "token": token, "now": clock_ms(), "stage": stage, "progress": progress, "message": message}).scalar())


def heartbeat(graph: Graph, job_id: str, token: str) -> bool:
    worker_seen(graph)
    return bool(graph.query("MATCH (j:RepositoryImport {id:$id,status:'running',lease_token:$token}) SET j.updated_at=$now RETURN j.id",
                            {"id": job_id, "token": token, "now": clock_ms()}).scalar())


def complete(graph: Graph, job_id: str, token: str, summary: dict, warnings: list[str]) -> bool:
    return bool(graph.query("""MATCH (j:RepositoryImport {id:$id,status:'running',lease_token:$token})
      SET j.status='complete', j.stage='complete', j.progress=100, j.message='Repository ready. Open its workspace to explore.',
          j.updated_at=$now, j.finished_at=$now, j.summary=$summary, j.warnings=$warnings REMOVE j.lease_token RETURN j.id""",
      {"id": job_id, "token": token, "now": clock_ms(), "summary": json.dumps(summary), "warnings": warnings}).scalar())


def fail(graph: Graph, job_id: str, token: str, message: str) -> None:
    graph.query("""MATCH (j:RepositoryImport {id:$id,status:'running',lease_token:$token})
      SET j.status='failed', j.stage='failed', j.message='The repository import could not finish.', j.error=$message,
          j.updated_at=$now, j.finished_at=$now REMOVE j.lease_token""",
      {"id": job_id, "token": token, "message": message, "now": clock_ms()})
