"""Import worker for scheduled GitHub Actions or a persistent host, never a serverless background task."""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from pathlib import Path

from untangle.graph.db import Graph
from untangle.ingest.github_api import GitHubClient
from untangle.ingest.pipeline import ingest_repo
from untangle.repositories import jobs
from untangle.repositories.models import LIMITS, ImportProblem
from untangle.repositories.service import fetch_public_repository

log = logging.getLogger("untangle.repositories")
STAGES = {
    "git": ("git", 8, "Reading commits and files from the default branch."),
    "github": ("github", 18, "Reading pull requests, reviews and issues."),
    "rows": ("head", 30, "Connecting contributors, modules and files."),
    "head": ("head", 38, "Extracting symbols, configuration, dependencies and documents."),
    "history": ("history", 48, "Tracing configuration and dependency changes through history."),
    "decisions": ("decisions", 62, "Connecting recorded decisions with their evidence."),
    "chunks": ("embeddings", 74, "Building the repository's search index with free local embeddings."),
    "write": ("write", 90, "Saving evidence and building the feature and import graph."),
}


def process_one(graph: Graph, *, ingester=ingest_repo, validator=fetch_public_repository) -> bool:
    jobs.expire_stalled(graph)
    jobs.worker_seen(graph)
    job = jobs.claim_next(graph)
    if not job:
        return False
    job_id, token = job["id"], job["lease_token"]
    stop = threading.Event()
    lost = threading.Event()

    def beat():
        while not stop.wait(25):
            try:
                if not jobs.heartbeat(graph, job_id, token):
                    lost.set()
                    return
            except Exception:
                log.exception("Import heartbeat failed")

    thread = threading.Thread(target=beat, daemon=True)
    thread.start()

    def progress(message: str):
        if lost.is_set():
            raise RuntimeError("Import lease was lost")
        stage = message.split("]", 1)[0].lstrip("[")
        if stage in STAGES and message.endswith(" started"):
            key, percent, text = STAGES[stage]
            if not jobs.update_progress(graph, job_id, token, key, percent, text):
                raise RuntimeError("Import lease was lost")

    try:
        metadata = validator(job["repo"])
        if metadata["full_name"].lower() != job["repo"].lower():
            raise ImportProblem(400, "The repository moved after it was queued. Add its current GitHub URL to retry.")
        # Fresh clones avoid stale GitHub discussion caches and stale Git state across refreshes.
        with tempfile.TemporaryDirectory(prefix="untangle-import-") as temp:
            with GitHubClient(job["repo"], cache_dir=Path(temp) / "github", use_cache=False) as client:
                result = ingester(job["repo"], graph=graph, max_commits=LIMITS["max_commits"], max_prs=LIMITS["max_prs"],
                                  max_issues=LIMITS["max_issues"], llm_prs=0, embed=True, progress=progress, cache_dir=Path(temp), github_client=client)
        warnings = result.get("warnings", [])
        warnings.append("Static imports describe the indexed version. Feature impact is an estimate, not a tested revert.")
        graph.query("MATCH (r:Repo {full_name:$repo}) SET r.description=$description, r.import_limits=$limits, r.import_warnings=$warnings",
                    {"repo": job["repo"], "description": metadata.get("description"), "limits": json.dumps(LIMITS), "warnings": warnings})
        summary = {key: result[key] for key in ("head_sha", "commits", "files", "prs", "issues", "people", "symbols", "config_keys", "dependencies", "documents", "chunks")}
        summary["decisions"] = result["decisions"]["recorded"]
        if not jobs.complete(graph, job_id, token, summary, warnings):
            raise RuntimeError("Import lease was lost before completion")
    except Exception as exc:
        log.error("Import %s failed (%s)", job_id, type(exc).__name__)
        message = str(exc) if isinstance(exc, ImportProblem) else "Repository analysis could not finish. Please retry; if it repeats, contact the deployment owner with this import ID."
        jobs.fail(graph, job_id, token, message)
    finally:
        stop.set()
        thread.join(timeout=2)
        jobs.worker_seen(graph)
    return True


def register(subparsers) -> None:
    parser = subparsers.add_parser("import-worker", help="process durable repository import jobs")
    parser.add_argument("--max-jobs", type=int, default=6)
    parser.set_defaults(func=run)


def run(args) -> int:
    from untangle.graph.db import connect
    graph = connect(require=True)
    try:
        graph.ensure_schema()
        done = 0
        while done < max(1, min(args.max_jobs, 6)) and process_one(graph):
            done += 1
        print(json.dumps({"processed": done}))
    finally:
        graph.close()
    return 0
