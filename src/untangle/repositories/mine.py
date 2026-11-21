"""A person's repositories: their public GitHub repositories, the ones they saved, and what changed since import.

Saved repositories belong to one account: `(u:User)-[:SAVED]->(s:SavedRepository {id, repo, repo_key, saved_at,
seen_sha, seen_at})`. The imported evidence itself stays shared, like every hosted import. GitHub is read with the
deployment's read-only token when one is configured; only public repositories are listed or compared."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from untangle.answer.text import iso
from untangle.auth.service import User
from untangle.graph.db import Graph
from untangle.repositories.models import ImportProblem
from untangle.repositories.service import normalize_repository

API_URL = "https://api.github.com"
MAX_SAVED = 30
_CACHE_SECONDS = 90.0
_cache: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()


def _cached(key: str, load):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    value = load()
    with _lock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[key] = (now + _CACHE_SECONDS, value)
    return value


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _github(path: str, params: dict | None = None) -> httpx.Response:
    from untangle.config import settings
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Untangle-repositories", "X-GitHub-Api-Version": "2022-11-28"}
    if settings().github_token:
        headers["Authorization"] = f"Bearer {settings().github_token}"
    try:
        with httpx.Client(timeout=15, follow_redirects=False, headers=headers) as client:
            return client.get(f"{API_URL}{path}", params=params)
    except httpx.HTTPError as exc:
        raise ImportProblem(503, "GitHub could not be reached. Please try again shortly.") from exc


def _owner(value: str) -> str:
    value = (value or "").strip().removeprefix("https://github.com/").strip("/").split("/")[0]
    if not value or len(value) > 39 or not all(c.isalnum() or c == "-" for c in value) or value.startswith("-"):
        raise ImportProblem(400, "Enter a GitHub user or organization name.")
    return value


def github_login(graph: Graph, user: User) -> str | None:
    return graph.read("MATCH (u:User {id:$id}) RETURN u.github_login AS login", {"id": user.id}).scalar()


def _indexed(graph: Graph, repos: list[str]) -> dict[str, dict]:
    rows = graph.read("""UNWIND $repos AS name
      MATCH (r:Repo) WHERE toLower(r.full_name) = toLower(name)
      RETURN r.full_name AS full_name, r.head_sha AS head_sha, r.ingested_at AS ingested_at,
             r.default_branch AS default_branch, r.commit_count AS commit_count""", {"repos": repos}).records
    return {r["full_name"].lower(): r for r in rows}


def _latest_jobs(graph: Graph, keys: list[str]) -> dict[str, dict]:
    rows = graph.read("""UNWIND $keys AS key
      MATCH (j:RepositoryImport {repo_key: key})
      WITH key, j ORDER BY j.created_at DESC
      WITH key, collect(j)[0] AS j
      RETURN key, j.id AS id, j.status AS status, j.progress AS progress, j.message AS message""", {"keys": keys}).records
    return {r["key"]: {k: r[k] for k in ("id", "status", "progress", "message")} for r in rows}


def _saved_keys(graph: Graph, user: User) -> set[str]:
    rows = graph.read("MATCH (:User {id:$id})-[:SAVED]->(s:SavedRepository) RETURN s.repo_key AS key", {"id": user.id}).records
    return {r["key"] for r in rows}


def github_repositories(graph: Graph, user: User, owner: str | None = None) -> dict:
    """Public repositories of `owner`, or of the signed-in person's connected GitHub account."""
    login = github_login(graph, user)
    name = _owner(owner) if owner else login
    if not name:
        return {"owner": None, "connected": False, "repositories": []}

    def load():
        response = _github(f"/users/{name}/repos", {"per_page": 100, "sort": "pushed", "type": "owner"})
        if response.status_code == 404:
            raise ImportProblem(404, "GitHub has no user or organization with that name.")
        if response.status_code != 200:
            raise ImportProblem(503, "GitHub is temporarily unavailable or rate limited. Please try again later.")
        return [{"full_name": r["full_name"], "description": (r.get("description") or "")[:300], "language": r.get("language"),
                 "stars": r.get("stargazers_count", 0), "fork": bool(r.get("fork")), "archived": bool(r.get("archived")),
                 "size_kb": r.get("size", 0), "default_branch": r.get("default_branch") or "main",
                 "pushed_at": r.get("pushed_at"), "url": r.get("html_url")}
                for r in response.json() if isinstance(r, dict) and not r.get("private")]

    repos = _cached(f"owner:{name.lower()}", load)
    indexed = _indexed(graph, [r["full_name"] for r in repos])
    jobs = _latest_jobs(graph, [r["full_name"].lower() for r in repos])
    saved = _saved_keys(graph, user)
    out = []
    for repo in repos:
        key = repo["full_name"].lower()
        out.append({**repo, "imported": key in indexed, "saved": key in saved, "job": jobs.get(key),
                    "ingested_at_iso": iso(indexed[key]["ingested_at"]) if key in indexed else None})
    return {"owner": name, "connected": bool(login), "self": bool(login) and name.lower() == login.lower(), "repositories": out}


def save(graph: Graph, user: User, repository: str) -> dict:
    repo = normalize_repository(repository)
    key = repo.lower()
    count = graph.read("MATCH (:User {id:$id})-[:SAVED]->(s:SavedRepository) RETURN count(s) AS n", {"id": user.id}).scalar() or 0
    if key not in _saved_keys(graph, user) and count >= MAX_SAVED:
        raise ImportProblem(429, f"You can keep up to {MAX_SAVED} repositories. Remove one to save another.")
    graph.query("""MATCH (u:User {id:$user_id})
      MERGE (s:SavedRepository {id: $id})
      ON CREATE SET s.saved_at = $now, s.user_id = $user_id
      SET s.repo = $repo, s.repo_key = $key
      MERGE (u)-[:SAVED]->(s)""", {"user_id": user.id, "id": f"{user.id}|{key}", "repo": repo, "key": key, "now": int(time.time() * 1000)})
    return {"repo": repo, "saved": True}


def unsave(graph: Graph, user: User, repository: str) -> bool:
    key = normalize_repository(repository).lower()
    return bool(graph.query("""MATCH (:User {id:$user_id})-[:SAVED]->(s:SavedRepository {repo_key:$key})
      DETACH DELETE s RETURN count(*) AS n""", {"user_id": user.id, "key": key}).scalar())


def _compare(repo: str, base: str, head: str) -> dict:
    def load():
        response = _github(f"/repos/{repo}/compare/{base}...{head}", {"per_page": 100})
        if response.status_code == 404:
            return {"available": False, "reason": "GitHub cannot compare the imported version with the current branch (history may have been rewritten)."}
        if response.status_code != 200:
            return {"available": False, "reason": "GitHub is temporarily unavailable or rate limited."}
        data = response.json()
        commits = []
        for c in reversed(data.get("commits") or []):
            info = c.get("commit") or {}
            author = (c.get("author") or {}).get("login") or (info.get("author") or {}).get("name") or "unknown"
            commits.append({"sha": c.get("sha"), "short": (c.get("sha") or "")[:7], "message": (info.get("message") or "").split("\n", 1)[0][:200],
                            "author": author, "date": (info.get("author") or {}).get("date"), "url": c.get("html_url")})
        files = [{"path": f.get("filename"), "status": f.get("status"), "additions": f.get("additions", 0), "deletions": f.get("deletions", 0)}
                 for f in (data.get("files") or [])[:40]]
        return {"available": True, "ahead_by": int(data.get("ahead_by") or 0), "behind_by": int(data.get("behind_by") or 0),
                "commits": commits[:30], "files": files, "files_changed": len(data.get("files") or []),
                "compare_url": data.get("html_url")}
    return _cached(f"compare:{repo.lower()}:{base}:{head}", load)


def saved_repositories(graph: Graph, user: User) -> dict:
    rows = graph.read("""MATCH (:User {id:$id})-[:SAVED]->(s:SavedRepository)
      RETURN s.repo AS repo, s.repo_key AS key, s.saved_at AS saved_at, s.seen_sha AS seen_sha, s.seen_at AS seen_at
      ORDER BY s.saved_at DESC""", {"id": user.id}).records
    repos = [r["repo"] for r in rows]
    indexed = _indexed(graph, repos)
    jobs = _latest_jobs(graph, [r["key"] for r in rows])

    def entry(row: dict) -> dict:
        key = row["key"]
        repo = indexed.get(key)
        result = {"repo": repo["full_name"] if repo else row["repo"], "saved_at_iso": iso(row["saved_at"]), "job": jobs.get(key),
                  "imported": bool(repo), "ingested_at_iso": iso(repo["ingested_at"]) if repo else None,
                  "indexed_sha": repo["head_sha"] if repo else None, "commit_count": repo["commit_count"] if repo else 0,
                  "changes": None}
        if repo and repo.get("head_sha"):
            changes = _compare(result["repo"], repo["head_sha"], repo.get("default_branch") or "HEAD")
            result["changes"] = {k: changes[k] for k in ("available", "ahead_by", "reason") if k in changes}
            seen = row.get("seen_sha")
            result["unseen"] = bool(changes.get("available") and changes.get("commits") and changes["commits"][0]["sha"] != seen)
        return result

    with ThreadPoolExecutor(max_workers=6) as pool:
        entries = list(pool.map(entry, rows))
    return {"repositories": entries, "max": MAX_SAVED}


def changes(graph: Graph, user: User, repository: str) -> dict:
    """Commits and files on GitHub's default branch since the version Untangle indexed; marks them as seen."""
    repo = normalize_repository(repository)
    indexed = _indexed(graph, [repo]).get(repo.lower())
    if not indexed or not indexed.get("head_sha"):
        raise ImportProblem(404, "This repository has not finished importing yet.")
    result = _compare(indexed["full_name"], indexed["head_sha"], indexed.get("default_branch") or "HEAD")
    latest = result["commits"][0]["sha"] if result.get("commits") else indexed["head_sha"]
    graph.query("""MATCH (:User {id:$user_id})-[:SAVED]->(s:SavedRepository {repo_key:$key})
      SET s.seen_sha = $sha, s.seen_at = $now""", {"user_id": user.id, "key": repo.lower(), "sha": latest, "now": int(time.time() * 1000)})
    recent = graph.read("""MATCH (c:Commit {repo:$repo}) WHERE c.authored_at >= 0
      RETURN c.sha AS sha, c.message AS message, c.authored_at AS authored_at
      ORDER BY c.authored_at DESC LIMIT 10""", {"repo": indexed["full_name"]}).records
    return {"repo": indexed["full_name"], "indexed_sha": indexed["head_sha"], "ingested_at_iso": iso(indexed["ingested_at"]),
            "default_branch": indexed.get("default_branch"), **result,
            "indexed_recent": [{"sha": r["sha"], "short": (r["sha"] or "")[:7], "message": (r["message"] or "").split("\n", 1)[0][:200],
                                "date": iso(r["authored_at"])} for r in recent]}
