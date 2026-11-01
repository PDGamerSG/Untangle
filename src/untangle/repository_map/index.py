"""Read source as data. Python AST and literal JS/TS imports; never execute repository code."""

from __future__ import annotations

import ast
import json
import posixpath
import re
from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any

JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
SUPPORTED = (*JS_EXTS, ".py")
MAX_MAP_FILES = 2000
_TOKEN = re.compile(r"(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|(?P<string>'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`)|(?P<word>[\w$]+)|(?P<punct>[^\s])")


def _jsonc(text: str) -> Any:
    text = _TOKEN.sub(lambda m: " " if m.lastgroup == "comment" else m.group(), text)
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def _js_imports(text: str) -> list[tuple[str, int]]:
    tokens = [m for m in _TOKEN.finditer(text) if m.lastgroup != "comment"]
    out = []
    for i, token in enumerate(tokens):
        if token.lastgroup != "word" or token.group() not in {"import", "export", "require"}:
            continue
        rest = tokens[i + 1:i + 100]
        if not rest:
            continue
        candidate = None
        if rest[0].lastgroup == "string" and token.group() == "import":
            candidate = rest[0]
        elif rest[0].group() == "(" and len(rest) > 2 and rest[1].lastgroup == "string" and rest[2].group() == ")":
            candidate = rest[1]
        elif token.group() != "require":
            for j, part in enumerate(rest[:-1]):
                if part.group() in {";", "import", "export"}:
                    break
                if part.group() == "from" and rest[j + 1].lastgroup == "string":
                    candidate = rest[j + 1]
                    break
        if candidate and candidate.group()[0] != "`":
            specifier = candidate.group()[1:-1]
            if "\\" not in specifier:
                out.append((specifier, text.count("\n", 0, token.start()) + 1))
    return out


def _python_imports(path: str, text: str) -> list[tuple[str, int]]:
    tree = ast.parse(text)
    parent = str(PurePosixPath(path).parent)
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend((a.name.replace(".", "/"), node.lineno) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = (node.module or "").replace(".", "/")
            if node.level:
                base = posixpath.normpath(posixpath.join(parent, *([".."] * (node.level - 1)), base))
                base = "/" + base  # repository-relative, not a filesystem path
            result.append((base, node.lineno))
            result.extend((f"{base}/{a.name}", node.lineno) for a in node.names if a.name != "*")
    return result


def build_index(repo: str, head_sha: str, content: dict[str, str], paths: list[str], manifest: str | None) -> dict:
    known = set(paths)
    warnings: list[str] = []
    aliases = []
    for path, text in content.items():
        if PurePosixPath(path).name not in {"tsconfig.json", "jsconfig.json"}:
            continue
        try:
            options = _jsonc(text).get("compilerOptions", {})
            root = str(PurePosixPath(path).parent)
            base = posixpath.normpath(posixpath.join(root, options.get("baseUrl", ".")))
            aliases.append((root, base, options.get("paths", {})))
        except (ValueError, TypeError, AttributeError):
            warnings.append(f"Could not read aliases in {path}.")
    aliases.sort(key=lambda row: len(row[0]), reverse=True)
    unresolved_examples: list[str] = []

    def resolve(path: str, spec: str) -> str | None:
        python = path.endswith(".py")
        roots = []
        if python:
            roots = [spec[1:]] if spec.startswith("/") else [spec, f"src/{spec}"]
            endings = (".py", "/__init__.py")
        else:
            endings = ("", *JS_EXTS, *(f"/index{ext}" for ext in JS_EXTS), ".css", ".json")
            if spec.startswith("."):
                roots.append(posixpath.join(str(PurePosixPath(path).parent), spec))
            else:
                for root, base, mapping in aliases:
                    if root != "." and not path.startswith(root + "/"):
                        continue
                    for pattern, targets in mapping.items():
                        prefix, _, suffix = pattern.partition("*")
                        if ("*" not in pattern and spec != pattern) or not spec.startswith(prefix) or not spec.endswith(suffix):
                            continue
                        middle = spec[len(prefix):len(spec) - len(suffix) if suffix else None]
                        roots.extend(posixpath.join(base, target.replace("*", middle)) for target in targets)
                    break
        for root in roots:
            root = posixpath.normpath(root)
            candidates = [root + ending for ending in endings]
            if not python and root.endswith((".js", ".jsx")):
                candidates.extend(str(PurePosixPath(root).with_suffix(ext)) for ext in (".ts", ".tsx"))
            for candidate in candidates:
                if candidate in known and candidate != path:
                    return candidate
        return None

    edges = {}
    scanned = unresolved = failed = 0
    for path, text in content.items():
        if not path.endswith(SUPPORTED):
            continue
        scanned += 1
        try:
            declarations = _python_imports(path, text) if path.endswith(".py") else _js_imports(text)
        except (SyntaxError, ValueError):
            failed += 1
            warnings.append(f"Could not parse {path}.")
            continue
        for spec, line in declarations:
            target = resolve(path, spec)
            if target:
                edges.setdefault((path, target), {"source": path, "target": target, "line": line, "specifier": spec})
            elif not path.endswith(".py") and spec.startswith((".", "@/")):
                unresolved += 1
                if len(unresolved_examples) < 8:
                    unresolved_examples.append(f"{path}:{line} → {spec}")

    features = []
    if manifest:
        try:
            raw = json.loads(manifest)
            if not isinstance(raw, dict) or not isinstance(raw.get("features"), list) or len(raw["features"]) > 60:
                raise ValueError("features must be a list of at most 60 definitions")
            for item in raw["features"]:
                key = item["id"]
                if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", key):
                    raise ValueError("feature ids must use letters, digits, underscores or hyphens")
                if not isinstance(item.get("entrypoints"), list) or not all(isinstance(p, str) for p in item["entrypoints"]):
                    raise ValueError("entrypoints must be a list of repository paths")
                missing = [p for p in item["entrypoints"] if p not in known]
                warnings.extend(f"Feature {key}: entry point {p} is missing at this HEAD." for p in missing)
                features.append({"id": f"feature:{repo}:{key}", "name": str(item["name"])[:120], "description": str(item.get("description", ""))[:500],
                                 "source": "manifest", "entrypoints": sorted({p for p in item["entrypoints"] if p in known})})
            if len({f["id"] for f in features}) != len(features):
                raise ValueError("duplicate feature ids")
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"Invalid .untangle/features.json: {exc}") from exc
    else:
        groups = defaultdict(list)
        for path in paths:
            groups[str(PurePosixPath(path).parent)].append(path)
        for directory, members in sorted(groups.items())[:60]:
            features.append({"id": f"feature:{repo}:{directory}", "name": directory, "description": "Inferred directory group; not a verified product feature.",
                             "source": "directory", "entrypoints": members})
        warnings.append("No feature manifest: showing up to 60 directory groups as code areas.")
    warnings.extend(f"Unresolved local import: {item}" for item in unresolved_examples)
    warnings.append("External and unresolved Python imports are not included. Dynamic dispatch and cross-service calls are not indexed.")
    return {"head_sha": head_sha, "features": features, "imports": list(edges.values()), "warnings": warnings,
            "coverage": {"head_files": len(paths), "scanned_files": scanned, "parse_failures": failed,
                         "unsupported_files": sum(not p.endswith(SUPPORTED) for p in paths),
                         "unresolved_local_imports": unresolved, "resolved_imports": len(edges)}}
