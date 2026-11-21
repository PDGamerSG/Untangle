from __future__ import annotations

import io
import json
import zipfile

import pytest

from untangle.repository_map.export import vault_zip
from untangle.repository_map.index import build_index


def test_directory_groups_cover_every_file_beyond_sixty_directories():
    paths = [f"area-{i}/file.go" for i in range(85)]
    result = build_index("o/r", "a", {}, paths, None)
    assert {p for f in result["features"] for p in f["entrypoints"]} == set(paths)


def test_map_scans_every_eligible_file_in_bounded_batches():
    from untangle.repository_map.service import index_repository_map

    class Git:
        def files_at_head(self):
            return {f"file_{i:04}.py": 20 for i in range(2101)}

        def read_at(self, paths, **kwargs):
            assert len(paths) <= 250
            return {p: "import file_2100\n" for p in paths}

        def head_sha(self):
            return "a" * 40

        def show(self, *args):
            return None

    class Graph:
        def run_named(self, *args, **kwargs):
            pass

    result = index_repository_map("o/r", Git(), Graph())
    assert result["coverage"]["scanned_files"] == 2101
    assert result["coverage"]["resolved_imports"] == 2100


def test_map_pages_cover_all_files_and_edges(graph, test_repo):
    from untangle.repository_map.service import complete_repository_map, repository_map

    graph.query("CREATE (:Repo {id:'repo:'+$repo, full_name:$repo,map_head_sha:'a',map_coverage:'{}'})", {"repo": test_repo})
    graph.query("""UNWIND range(0,2100) AS i
      CREATE (:File {id:$repo+toString(i),repo:$repo,path:toString(i)+'.py',alive:true})""", {"repo": test_repo})
    graph.query("""MATCH (f:File {repo:$repo}), (target:File {repo:$repo})
      WHERE target.path IN ['0.py','1.py','2.py','3.py','4.py','5.py'] AND f <> target
      CREATE (f)-[:IMPORTS {indexer:'repository-map-v1',line:1,specifier:'target'}]->(target)""", {"repo": test_repo})
    data = repository_map(test_repo, graph)
    files = data["files"][:]
    imports = data["imports"][:]
    while data.get("structure_has_more"):
        data = repository_map(test_repo, graph, structure_page=data["structure_page"] + 1)
        files.extend(data["files"])
        imports.extend(data["imports"])
    assert len(files) == len({f["path"] for f in files}) == 2101
    assert len(imports) == len({(e["source"], e["target"]) for e in imports}) == 12600
    complete = complete_repository_map(test_repo, graph)
    assert len(complete["files"]) == 2101 and len(complete["imports"]) == 12600
    with zipfile.ZipFile(io.BytesIO(vault_zip(complete))) as archive:
        assert len([p for p in archive.namelist() if p.startswith("files/")]) == 2101


def test_imports_resolve_python_relative_ts_aliases_and_skip_comments():
    content = {
        "src/pkg/__init__.py": "",
        "src/pkg/a.py": "from . import b\nfrom pkg.b import value\n# import pkg.missing\n",
        "src/pkg/b.py": "value = 1\n",
        "web/tsconfig.json": json.dumps({"compilerOptions": {"paths": {"@/*": ["./src/*"]}}}),
        "web/src/page.tsx": "// import './ghost'\nconst text = \"import './ghost'\";\nimport { read } from '@/lib/read';\nexport { read } from './lib/read';\nimport('./lib/read');",
        "web/src/lib/read.ts": "export const read = 1;",
    }
    result = build_index("o/r", "a" * 40, content, list(content), None)
    pairs = {(e["source"], e["target"]) for e in result["imports"]}
    assert pairs == {("src/pkg/a.py", "src/pkg/b.py"), ("src/pkg/a.py", "src/pkg/__init__.py"), ("web/src/page.tsx", "web/src/lib/read.ts")}
    assert all(edge["line"] > 0 for edge in result["imports"])
    assert result["coverage"]["unresolved_local_imports"] == 0


def test_feature_manifest_is_explicit_and_missing_entrypoints_are_reported():
    manifest = json.dumps({"features": [{"id": "ask", "name": "Ask", "entrypoints": ["app.py", "gone.py"]}]})
    result = build_index("o/r", "a" * 40, {"app.py": "import missing_local\n"}, ["app.py"], manifest)
    assert result["features"][0]["source"] == "manifest"
    assert result["features"][0]["entrypoints"] == ["app.py"]
    assert any("gone.py" in warning for warning in result["warnings"])
    fallback = build_index("o/r", "b" * 40, {}, ["cmd/main.go"], None)
    assert fallback["features"][0]["source"] == "directory"
    assert fallback["coverage"]["unsupported_files"] == 1


def test_invalid_manifest_and_unresolved_imports_are_visible():
    with pytest.raises(ValueError, match="entrypoints must be a list"):
        build_index("o/r", "a", {}, [], json.dumps({"features": [{"id": "x", "name": "x", "entrypoints": "app.py"}]}))
    data = build_index("o/r", "a", {"a.ts": "import './missing';"}, ["a.ts"], None)
    assert data["coverage"]["unresolved_local_imports"] == 1
    assert any("a.ts:1" in w for w in data["warnings"])


async def test_map_http_parameters_and_vault_download(monkeypatch):
    import httpx

    from untangle.api import main

    payload = {"repo": "o/r", "head_sha": "a" * 40, "features": [], "files": [], "imports": [], "commits": [], "offset": 0, "total_commits": 0, "coverage": {}, "warnings": []}
    monkeypatch.setattr(main.service, "get_graph", lambda: object())
    monkeypatch.setattr(main, "repository_map", lambda repo, graph, **kw: {**payload, "offset": kw["offset"]})
    monkeypatch.setattr(main, "complete_repository_map", lambda repo, graph, **kw: {**payload, "offset": kw["offset"]})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        assert (await client.get("/repository-map", params={"repo": "o/r", "offset": -1})).status_code == 422
        assert (await client.get("/repository-map", params={"repo": "o/r", "limit": 201})).status_code == 422
        result = await client.get("/repository-map", params={"repo": "o/r", "offset": 40})
        assert result.status_code == 200 and result.json()["offset"] == 40
        export = await client.get("/repository-map/obsidian", params={"repo": "o/r"})
        assert export.status_code == 200 and export.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
            assert "README.md" in archive.namelist()


def test_export_has_safe_unique_notes_and_no_dangling_wikilinks():
    data = {"repo": "o/r", "head_sha": "a" * 40, "indexed_at_iso": "2026-11-01", "warnings": [],
            "coverage": {}, "total_commits": 2, "offset": 0, "has_more": False,
            "features": [{"id": "feature:o/r:ask", "name": "Ask [unsafe]", "description": "", "source": "manifest", "entrypoints": ["src/a.py"]}],
            "files": [{"path": "src/a.py", "alive": True}, {"path": "src/b.py", "alive": True}],
            "imports": [{"source": "src/a.py", "target": "src/b.py", "line": 1, "specifier": ".b"}],
            "commits": [{"sha": "b" * 40, "title": "change", "parents": ["a" * 40], "authored_at_iso": "2026-11-01", "author": "Sam", "files": [{"path": "src/b.py", "change": "M"}]}]}
    with zipfile.ZipFile(io.BytesIO(vault_zip(data))) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)) and all(".." not in path for path in names)
        import re
        for path in names:
            text = archive.read(path).decode()
            for target in re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", text):
                assert f"{target}.md" in names
        assert "not a tested revert" in archive.read("README.md").decode()


def test_map_indexes_git_parents_isolates_repositories_and_replaces_old_edges(graph, test_repo, tmp_path):
    from ingest_fixture import git, write
    from untangle.repository_map.service import refresh_map, repository_map

    git(tmp_path, "init", "-q", "-b", "main")
    write(tmp_path, "app.py", "import helper\n")
    write(tmp_path, "helper.py", "value = 1\n")
    write(tmp_path, ".untangle/features.json", json.dumps({"features": [{"id": "app", "name": "App", "entrypoints": ["app.py"]}]}))
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "initial", date="2026-10-01T10:00:00Z")
    parent = git(tmp_path, "rev-parse", "HEAD")
    refresh_map(test_repo, graph, tmp_path)
    first = repository_map(test_repo, graph, limit=1)
    assert first["features"][0]["name"] == "App"
    assert first["imports"] == [{"source": "app.py", "target": "helper.py", "line": 1, "specifier": "helper"}]
    assert first["commits"][0]["parents"] == [] and first["commits"][0]["parents_known"]
    write(tmp_path, "app.py", "value = 2\n")
    git(tmp_path, "commit", "-qam", "remove import", date="2026-10-02T10:00:00Z")
    refresh_map(test_repo, graph, tmp_path)
    current = repository_map(test_repo, graph, limit=1)
    assert current["imports"] == [] and len(current["features"]) == 1
    assert current["commits"][0]["parents"] == [parent]
    assert current["has_more"] and current["total_commits"] == 2
    assert repository_map(test_repo, graph, offset=1, limit=1)["commits"][0]["sha"] == parent
    from untangle.answer.service import NotFound

    with pytest.raises(NotFound):
        repository_map("different/repository", graph)


def test_legacy_repository_exposes_file_and_commit_map_without_a_manual_index(graph, test_repo):
    from untangle.repository_map.service import repository_map

    graph.query("""CREATE (:Repo {id:'repo:'+$repo, full_name:$repo, head_sha:$sha, ingested_at:1000})
      CREATE (f:File {id:'file:'+$repo+':src/main.go',repo:$repo,path:'src/main.go',alive:true})
      CREATE (:File {id:'file:'+$repo+':removed.go',repo:$repo,path:'removed.go',alive:false})
      CREATE (c:Commit {id:'commit:'+$repo+'@'+$sha,repo:$repo,sha:$sha,title:'Initial',authored_at:1000})
      CREATE (c)-[:TOUCHED {change:'A'}]->(f)""", {"repo": test_repo, "sha": "a" * 40})
    data = repository_map(test_repo, graph)
    assert data["head_sha"] == "a" * 40
    assert data["index_status"] == "basic"
    assert data["features"][0]["entrypoints"] == ["src/main.go"]
    assert data["commits"][0]["files"][0]["path"] == "src/main.go"
    assert data["imports"] == []
    assert any("not yet indexed" in warning for warning in data["warnings"])
    assert repository_map(test_repo, graph, offset=1)["features"] == data["features"]
    with zipfile.ZipFile(io.BytesIO(vault_zip(data))) as archive:
        assert any(path.startswith("features/") for path in archive.namelist())


def test_invalid_optional_feature_manifest_does_not_prevent_repository_map(graph, test_repo, tmp_path):
    from ingest_fixture import git, write
    from untangle.repository_map.service import refresh_map, repository_map

    git(tmp_path, "init", "-q", "-b", "main")
    write(tmp_path, "main.go", "package main\n")
    write(tmp_path, ".untangle/features.json", '{"features": "invalid"}')
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "initial", date="2026-10-01T10:00:00Z")
    refresh_map(test_repo, graph, tmp_path)
    data = repository_map(test_repo, graph)
    assert data["index_status"] == "ready"
    assert data["features"] and all(f["source"] == "directory" for f in data["features"])
    assert any("Invalid .untangle/features.json" in warning for warning in data["warnings"])
