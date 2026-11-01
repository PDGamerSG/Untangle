"""Obsidian-readable notes. IDs determine filenames; source text never determines ZIP paths."""

from __future__ import annotations

import hashlib
import html
import io
import json
import re
import zipfile
from urllib.parse import quote


def _plain(text: object) -> str:
    return re.sub(r"([\\`*_[\]#|])", r"\\\1", html.escape(str(text or "")).replace("\n", " "))


def vault_zip(data: dict) -> bytes:
    notes: dict[str, str] = {}
    filenames: dict[tuple[str, str], str] = {}
    for kind, rows, key in [("features", data["features"], "id"), ("files", data["files"], "path"), ("commits", data["commits"], "sha")]:
        for row in rows:
            identity = str(row[key])
            digest = hashlib.sha256(identity.encode()).hexdigest()[:20]
            filenames[kind, identity] = f"{kind}/{digest}"

    def link(kind: str, identity: str, label: str | None = None) -> str:
        filename = filenames.get((kind, identity))
        safe_label = re.sub(r"[\[\]|\n\r]", " ", str(label or identity))
        return f"[[{filename}|{html.escape(safe_label)}]]" if filename else _plain(label or identity)

    def note(kind: str, identity: str, title: str, lines: list[str]) -> None:
        metadata = ["---", f"title: {json.dumps(title)}", f"tags: [untangle, {kind}]", f"repository: {json.dumps(data['repo'])}", "---"]
        notes[f"{filenames[kind, identity]}.md"] = "\n".join([*metadata, f"# {_plain(title)}", "", *lines, ""])

    source = f"https://github.com/{quote(data['repo'], safe='/')}/blob/{quote(data.get('head_sha') or '', safe='')}/"
    for feature in data["features"]:
        note("features", feature["id"], feature["name"], [
            _plain(feature.get("description")), f"Definition: {_plain(feature['source'])}", "", "## Entry points",
            *[f"- {link('files', p)}" for p in feature["entrypoints"]],
        ])
    for file in data["files"]:
        path = file["path"]
        note("files", path, path, [
            f"Present at indexed HEAD: {bool(file.get('alive'))}",
            f"[Source at indexed HEAD]({source}{quote(path, safe='/')})" if file.get("alive") else "Historical path; absent at indexed HEAD.",
            "", "## Imports",
            *[f"- {link('files', e['target'])} — line {e['line']}, {_plain(e['specifier'])}" for e in data["imports"] if e["source"] == path],
        ])
    for commit in data["commits"]:
        sha = commit["sha"]
        note("commits", sha, f"{sha[:7]} {commit['title']}", [
            f"SHA: {_plain(sha)}", f"Date: {_plain(commit.get('authored_at_iso'))}", f"Author: {_plain(commit.get('author'))}",
            f"[Commit on GitHub](https://github.com/{quote(data['repo'], safe='/')}/commit/{quote(sha, safe='')})", "",
            "## Parents (history, not runtime dependencies)",
            *[f"- {link('commits', parent, parent[:12])}" for parent in commit["parents"]], "", "## Changed files",
            *[f"- {link('files', f['path'])} — {_plain(f.get('change'))}" for f in commit["files"]],
        ])
    notes["README.md"] = "\n".join([
        "# Untangle repository map", f"Repository: {_plain(data['repo'])}", f"Indexed HEAD: {_plain(data.get('head_sha'))}",
        f"Indexed at: {_plain(data.get('indexed_at_iso'))}", "",
        "Extract this ZIP into a new folder and open that folder as an Obsidian vault. Open Graph view; group by tag:features, tag:files and tag:commits. Use Local graph to follow a feature or commit.",
        "", "This is static evidence, not a tested revert. Imports describe indexed HEAD, not every historical revision. A parent link records Git ancestry, not feature dependency. Missing paths do not prove safety.",
        f"History scope: {len(data['commits'])} commits from offset {data['offset']} of {data['total_commits']} indexed commits.",
        f"Coverage: {_plain(json.dumps(data.get('coverage', {})))}", *[f"- {_plain(w)}" for w in data.get("warnings", [])],
        "", "## Features", *[f"- {link('features', f['id'], f['name'])}" for f in data["features"]],
    ])
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, body in sorted(notes.items()):
            archive.writestr(path, body)
    return stream.getvalue()
