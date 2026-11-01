from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

import httpx

from untangle.answer.text import iso
from untangle.config import settings
from untangle.graph.db import Graph
from untangle.repositories.models import LIMITS, ImportProblem

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}\Z")


def normalize_repository(value: str) -> str:
    value = value.strip()
    if value.startswith("https://"):
        url = urlsplit(value)
        if url.netloc != "github.com" or url.query or url.fragment:
            raise ImportProblem(400, "Enter a GitHub repository URL without credentials, query parameters or fragments.")
        value = url.path.lstrip("/")
    value = value.rstrip("/").removesuffix(".git")
    if not _NAME.fullmatch(value) or value.split("/")[-1] in (".", ".."):
        raise ImportProblem(400, "Enter a GitHub repository as owner/name or https://github.com/owner/name.")
    return value


def fetch_public_repository(repo: str) -> dict:
    """Unauthenticated check intentionally cannot expose a private repo readable by the deployment's token."""
    repo = normalize_repository(repo)
    try:
        with httpx.Client(timeout=15, follow_redirects=False, headers={"Accept": "application/vnd.github+json", "User-Agent": "Untangle-repository-import"}) as client:
            response = client.get(f"https://api.github.com/repos/{repo}")
    except httpx.HTTPError as exc:
        raise ImportProblem(503, "GitHub could not be reached. Please try again shortly.") from exc
    if response.status_code in (301, 302, 307, 308):
        raise ImportProblem(400, "This repository has moved. Enter its current GitHub URL.")
    if response.status_code == 404:
        raise ImportProblem(404, "GitHub could not find a public repository at that URL. Check the name and its visibility.")
    if response.status_code != 200:
        raise ImportProblem(503, "GitHub is temporarily unavailable or rate limited. Please try again later.")
    try:
        data = response.json()
        full_name = normalize_repository(data.get("full_name", repo))
        if data.get("private") or data.get("disabled"):
            raise ImportProblem(400, "Only publicly accessible GitHub repositories can be added to this shared deployment.")
        if int(data.get("size", 0)) > LIMITS["max_repository_size_kb"]:
            raise ImportProblem(413, "This repository exceeds the hosted import size limit of 100 MB. Use the ingestion CLI for larger repositories.")
        if full_name.lower() != repo.lower():
            raise ImportProblem(400, "This repository has moved. Enter its current GitHub URL.")
        return {"full_name": full_name, "description": (data.get("description") or "")[:2000], "default_branch": data.get("default_branch") or "main",
                "size": int(data.get("size", 0)), "private": False}
    except (ValueError, TypeError, AttributeError) as exc:
        raise ImportProblem(503, "GitHub returned incomplete repository metadata. Please try again later.") from exc


def submit(value: str, graph: Graph) -> dict:
    from untangle.repositories.jobs import enqueue, expire_stalled
    repo = normalize_repository(value)
    if not settings().repo_imports_enabled:
        raise ImportProblem(503, "Repository imports are temporarily unavailable. Existing repositories remain available.")
    metadata = fetch_public_repository(repo)
    expire_stalled(graph)
    return enqueue(graph, metadata)


def status(graph: Graph) -> dict:
    from untangle.repositories.jobs import expire_stalled, list_jobs
    expire_stalled(graph)
    seen = graph.read("MATCH (c:ImportControl {id:'repositories'}) RETURN c.last_seen_at AS seen").scalar()
    return {"enabled": settings().repo_imports_enabled, "limits": LIMITS, "jobs": list_jobs(graph),
            "worker": {"last_seen_at_iso": iso(seen), "scheduling": "Imports are picked up by a scheduled worker, usually within a few minutes. GitHub scheduling can delay startup."}}


def overview(repo: str, graph: Graph) -> dict:
    from untangle.repositories.jobs import list_jobs
    repo = normalize_repository(repo)
    rows = graph.run_named("repository_overview", {"repo": repo}).records
    if not rows:
        raise ImportProblem(404, "This repository has not finished importing yet.")
    result = rows[0]
    result["ingested_at_iso"] = iso(result.pop("ingested_at"))
    coverage = json.loads(result.pop("map_coverage") or "{}")
    limits = json.loads(result.pop("import_limits") or "{}")
    result["coverage"] = {"commits": result["counts"].get("commits", 0), "max_commits": limits.get("max_commits"), "max_prs": limits.get("max_prs"), "max_issues": limits.get("max_issues"),
                          "map_scanned_files": coverage.get("scanned_files", 0), "unresolved_imports": coverage.get("unresolved_local_imports", 0)}
    warnings = result.get("warnings") or []
    if limits:
        warnings.append("Hosted imports include up to 1,000 recent commits, 50 pull requests and 100 GitHub issue entries; older history may be absent.")
    if result["counts"].get("dependencies", 0) > 50 or result["counts"].get("documents", 0) > 50:
        warnings.append("Inventory previews show up to 50 dependencies and 50 documents. Counts describe all indexed records.")
    warnings.append("Feature connections use static Python/JS/TS imports. Runtime calls and unsupported languages can add relationships not shown here.")
    if result["features"] and all(f["source"] == "directory" for f in result["features"]):
        warnings.append("Feature groups are inferred from directories. Add .untangle/features.json to define named product features.")
    latest = next((j for j in list_jobs(graph) if j["repo"] == repo), None)
    if latest and latest["status"] in ("failed", "running"):
        warnings.append("An import is incomplete. Existing records are still visible and may include partial updates.")
    result["warnings"] = warnings
    subjects = graph.read("""MATCH (d:Decision {repo:$repo,status:'active'})-[:ABOUT]->(k)
      WHERE k:ConfigKey OR k:Dependency
      OPTIONAL MATCH (k)-[:DECLARED_IN|SET_IN]->(f:File)
      RETURN labels(k)[0] AS kind, coalesce(k.key,k.name) AS name, coalesce(k.path,f.path) AS path
      ORDER BY d.valid_from DESC LIMIT 8""", {"repo": repo}).records
    questions = [f"{'Why do we use' if s['kind'] == 'Dependency' else 'What is'} {s['name']} in {s['path']}?" for s in subjects if s["name"] and s["path"]]
    result["suggested_questions"] = list(dict.fromkeys(questions))[:4]
    return result
