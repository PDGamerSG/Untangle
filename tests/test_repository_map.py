from __future__ import annotations

import io
import json
import zipfile

import pytest

from untangle.repository_map.export import vault_zip
from untangle.repository_map.index import build_index


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
