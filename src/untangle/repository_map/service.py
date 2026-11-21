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
from untangle.repository_map.index import SUPPORTED, build_index

FILES_PER_PAGE = 500
IMPORTS_PER_PAGE = 2000
FEATURES_PER_PAGE = 100


def index_repository_map(repo: str, git: GitRepo, graph: Graph, *, progress=None) -> dict:
    paths = git.files_at_head()
    interesting = [p for p, size in sorted(paths.items()) if not should_skip(p, size) and
                   (p.endswith(SUPPORTED) or p.endswith(("tsconfig.json", "jsconfig.json")))]
    content = {}
    for start in range(0, len(interesting), 250):
        content.update(git.read_at(interesting[start:start + 250], max_bytes=MAX_FILE_BYTES))
        if progress:
            progress(f"[map] Read {min(start + 250, len(interesting))} of {len(interesting)} eligible source files.")
    manifest = git.show("HEAD", ".untangle/features.json")
    try:
        data = build_index(repo, git.head_sha(), content, list(paths), manifest)
    except ValueError as exc:
        if not str(exc).startswith("Invalid .untangle/features.json:"):
            raise
        data = build_index(repo, git.head_sha(), content, list(paths), None)
        data["warnings"].append(f"{exc}. Using directory groups instead.")
    data["coverage"]["eligible_files_read"] = len(content)
    data["coverage"]["eligible_files"] = len(interesting)
    data["coverage"]["unreadable_files"] = len(interesting) - len(content)
    if len(content) != len(interesting):
        raise RuntimeError("Not all eligible source files could be read; retry the repository import.")
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


def repository_map(repo: str, graph: Graph, *, offset: int = 0, limit: int = 80, structure_page: int = 0) -> dict:
    params = {
        "repo": repo, "offset": offset, "limit": limit if structure_page == 0 else 0,
        "file_offset": structure_page * FILES_PER_PAGE, "file_limit": FILES_PER_PAGE,
        "import_offset": structure_page * IMPORTS_PER_PAGE, "import_limit": IMPORTS_PER_PAGE,
        "feature_offset": structure_page * FEATURES_PER_PAGE, "feature_limit": FEATURES_PER_PAGE,
    }
    rows = graph.run_named("repository_map", params, timeout=20000).records
    if not rows:
        from untangle.answer.service import NotFound
        raise NotFound(f"Repository {repo} has not been ingested.")
    data = rows[0]
    for key, name, column in (("files", "map_files", "file"), ("features", "map_features", "feature"),
                              ("imports", "map_imports", "edge"), ("commits", "map_commits", "commit")):
        data[key] = [row[column] for row in graph.run_named(name, params, timeout=20000).records]
    # A refresh may publish a new map between the independent reads.
    latest = graph.run_named("repository_map", params, timeout=20000).records
    if not latest or any(latest[0].get(key) != data.get(key) for key in (
        "head_sha", "indexed_at", "repository_head_sha", "repository_ingested_at", "total_files", "total_imports", "total_features", "total_commits",
    )):
        from untangle.repositories.models import ImportProblem
        raise ImportProblem(409, "The repository changed while its map was loading. Please retry.")
    # Older ingestions already have files and commits. Expose that evidence immediately;
    # never invent import edges or claim a source scan happened when it did not.
    snapshot = data.pop("repository_head_sha", None)
    ingested_at = data.pop("repository_ingested_at", None)
    data["index_status"] = "ready" if data["head_sha"] else "basic"
    if not data["head_sha"]:
        data["head_sha"] = snapshot
        data["indexed_at"] = ingested_at
        # Directory groups are inferred after all file pages have been assembled.
        data["features"] = []
        data["imports"] = []
        data["warnings"] = [*(data["warnings"] or []), "Source import connections are not yet indexed. This map shows stored files, directory groups and commit changes; indirect impact is unknown."]
    data.update(repo=repo, offset=offset, has_more=offset + len(data["commits"]) < data["total_commits"],
                structure_page=structure_page,
                structure_has_more=max(
                    (data["total_files"] + FILES_PER_PAGE - 1) // FILES_PER_PAGE,
                    (data["total_imports"] + IMPORTS_PER_PAGE - 1) // IMPORTS_PER_PAGE,
                    (data["total_features"] + FEATURES_PER_PAGE - 1) // FEATURES_PER_PAGE,
                ) > structure_page + 1)
    data["indexed_at_iso"] = iso(data.pop("indexed_at"))
    data["coverage"] = json.loads(data["coverage"] or "{}")
    data["warnings"] = data["warnings"] or []
    if data["index_status"] == "basic" and not data["structure_has_more"] and structure_page == 0:
        data["features"] = build_index(repo, snapshot or "", {}, [f["path"] for f in data["files"] if f.get("alive")], None)["features"]
        data["total_features"] = len(data["features"])
    for commit in data["commits"]:
        commit["authored_at_iso"] = iso(commit.pop("authored_at"))
        commit["parents_known"] = commit["parent_shas"] is not None
        commit["parents"] = commit.pop("parent_shas") or []
    return data


def complete_repository_map(repo: str, graph: Graph, *, offset: int = 0, limit: int = 200) -> dict:
    """Assemble bounded pages for downloads; reject a snapshot changing mid-read."""
    data = repository_map(repo, graph, offset=offset, limit=limit)
    page = data
    while page["structure_has_more"]:
        page = repository_map(repo, graph, offset=offset, limit=limit, structure_page=page["structure_page"] + 1)
        if any(page.get(key) != data.get(key) for key in ("head_sha", "indexed_at_iso", "total_files", "total_imports", "total_features")):
            from untangle.repositories.models import ImportProblem
            raise ImportProblem(409, "The repository changed while its map was loading. Please retry.")
        for key in ("files", "imports", "features"):
            data[key].extend(page[key])
    known = {f["path"] for f in data["files"]}
    if len(known) != data["total_files"] or len(known) != len(data["files"]) or len(data["imports"]) != data["total_imports"] or any(
        e["source"] not in known or e["target"] not in known for e in data["imports"]
    ):
        from untangle.repositories.models import ImportProblem
        raise ImportProblem(409, "The repository map is incomplete. Please retry or refresh its import.")
    if data["index_status"] == "basic":
        data["features"] = build_index(repo, data["head_sha"] or "", {}, [f["path"] for f in data["files"] if f.get("alive")], None)["features"]
        data["total_features"] = len(data["features"])
    data["structure_has_more"] = False
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
