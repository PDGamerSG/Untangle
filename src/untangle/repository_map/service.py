from __future__ import annotations

import json
import time
from pathlib import Path

from untangle import ids
from untangle.answer.text import iso
from untangle.graph.db import Graph
from untangle.ingest.git_history import GitRepo, clone_or_fetch
from untangle.ingest.loader import Loader, People, commit_rows, file_rows
from untangle.ingest.symbols import MAX_FILE_BYTES, should_skip
from untangle.repository_map.index import MAX_MAP_FILES, SUPPORTED, build_index


def index_repository_map(repo: str, git: GitRepo, graph: Graph) -> dict:
    paths = git.files_at_head()
    interesting = [p for p, size in sorted(paths.items()) if not should_skip(p, size) and
                   (p.endswith(SUPPORTED) or p.endswith(("tsconfig.json", "jsconfig.json")))][:MAX_MAP_FILES]
    content = git.read_at(interesting, max_bytes=MAX_FILE_BYTES)
    manifest = git.show("HEAD", ".untangle/features.json")
    data = build_index(repo, git.head_sha(), content, list(paths), manifest)
    if len(paths) > MAX_MAP_FILES:
        data["warnings"].append("Only the first 2000 eligible source files are scanned; the displayed file graph is also capped at 2000 files.")
    data["coverage"]["eligible_files_read"] = len(content)
    graph.run_named("index_repository_map", {
        "repo_id": ids.repo_id(repo), "repo": repo, "head_sha": data["head_sha"], "indexed_at": int(time.time() * 1000),
        "coverage": json.dumps(data["coverage"]), "warnings": data["warnings"],
        "features": data["features"], "imports": data["imports"],
    }, write=True)
    return data


def refresh_map(repo: str, graph: Graph, path: Path | None = None) -> dict:
    """Refresh Git/files/imports without rewriting decisions, embeddings or handovers."""
    git = GitRepo(path) if path else clone_or_fetch(repo)
    commits = git.log()
    identities = graph.read("MATCH (i:Identity {kind: 'email'})-[:IDENTITY_OF]->(p:Person) WHERE p.login IS NOT NULL RETURN i.value AS email, p.login AS login, p.name AS name").records
    people = People({r["email"]: r["login"] for r in identities}, {r["login"]: r["name"] for r in identities})
    rows = commit_rows(repo, commits, people)
    files = file_rows(repo, commits, git.files_at_head(), people)
    loader = Loader(graph, repo)
    loader.people(people)
    loader.write("11_upsert_commits", rows)
    loader.files(files)
    return index_repository_map(repo, git, graph)


def repository_map(repo: str, graph: Graph, *, offset: int = 0, limit: int = 80) -> dict:
    rows = graph.run_named("repository_map", {"repo": repo, "offset": offset, "limit": limit}, timeout=20000).records
    if not rows:
        from untangle.answer.service import NotFound
        raise NotFound(f"Repository {repo} has not been ingested.")
    data = rows[0]
    data.update(repo=repo, offset=offset, has_more=offset + len(data["commits"]) < data["total_commits"])
    data["indexed_at_iso"] = iso(data.pop("indexed_at"))
    data["coverage"] = json.loads(data["coverage"] or "{}")
    data["warnings"] = data["warnings"] or []
    known = {f["path"] for f in data["files"]}
    before = len(data["imports"])
    data["imports"] = [e for e in data["imports"] if e["source"] in known and e["target"] in known]
    if data["total_files"] > len(known) or before >= 12000 or before != len(data["imports"]):
        data["warnings"].append("The graph is truncated. Missing paths cannot be treated as unaffected.")
    for feature in data["features"]:
        feature["entrypoints"] = [p for p in feature["entrypoints"] if p in known]
    for commit in data["commits"]:
        commit["authored_at_iso"] = iso(commit.pop("authored_at"))
        commit["parents_known"] = commit["parent_shas"] is not None
        commit["parents"] = commit.pop("parent_shas") or []
    return data


def register(subparsers) -> None:
    parser = subparsers.add_parser("map-index", help="refresh feature/import/commit graph without changing decisions or embeddings")
    parser.add_argument("repo")
    parser.add_argument("--path", type=Path, help="read an existing local Git repository")
    parser.set_defaults(func=run)


def run(args) -> int:
    from untangle.graph.db import connect
    graph = connect(require=True)
    try:
        graph.ensure_schema()
        data = refresh_map(args.repo, graph, args.path)
        print(json.dumps({"head_sha": data["head_sha"], "coverage": data["coverage"], "features": len(data["features"]), "warnings": data["warnings"]}, indent=2))
    finally:
        graph.close()
    return 0
