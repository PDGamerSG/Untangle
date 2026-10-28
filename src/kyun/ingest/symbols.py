"""Regex extraction of symbols, configuration keys and declared dependencies from file contents.

No parser per language is needed for the questions Kyun answers ("why is `retry_limit` 3?", "who owns
`Mailer`?"): a top-level declaration regex per language, a flattener for YAML/TOML/JSON/.env/INI files and
a handful of manifest readers. Everything is pure: callers pass `(path, text)`, nothing touches the disk."""

from __future__ import annotations

import configparser
import json
import logging
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import yaml

log = logging.getLogger("kyun.ingest.symbols")

MAX_SYMBOLS_PER_FILE = 400
MAX_KEYS_PER_FILE = 300
MAX_FILE_BYTES = 400 * 1024
MAX_KEY_DEPTH = 4
MAX_VALUE_CHARS = 200

_SKIP_DIR_PARTS = {
    "node_modules", "vendor", "vendors", "third_party", "thirdparty", "third-party", "dist", "build", "out",
    "target", "bower_components", ".venv", "venv", "site-packages", "__pycache__", "generated", ".git",
    ".idea", ".vscode", "coverage", "__snapshots__", "testdata", "fixtures", "fixture", "static/vendor",
}
_SKIP_FILE_PATTERNS = re.compile(
    r"(\.min\.(js|css)$|-min\.js$|\.bundle\.js$|\.pb\.go$|_generated\.go$|\.generated\.|zz_generated|"
    r"\.d\.ts$|\.map$|\.lock$|^package-lock\.json$|^yarn\.lock$|^pnpm-lock\.yaml$|^go\.sum$|^composer\.lock$|"
    r"\.snap$|\.svg$|\.pyc$|\.wasm$)",
    re.IGNORECASE,
)
# Directories whose YAML/JSON is data, not configuration (translations, snapshots, test fixtures).
_NOISY_CONFIG_PARTS = {"i18n", "locales", "locale", "translations", "translation", "lang", "langs", "l10n", "messages",
                       "fixtures", "testdata", "snapshots", "__snapshots__", "schemas", "schema", "mocks", "__mocks__"}
_DERIVED_SUFFIXES = (".sample", ".example", ".dist", ".template", ".tmpl", ".default", ".defaults", ".bak", ".orig")

_DOC_EXTS = {".md", ".markdown", ".rst", ".txt", ".adoc", ".mdx"}
_LANG_BY_EXT = {
    ".go": "go", ".py": "python", ".ts": "typescript", ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".vue": "vue", ".rs": "rust", ".java": "java", ".kt": "kotlin",
    ".kts": "kotlin", ".rb": "ruby", ".php": "php", ".cs": "csharp", ".c": "c", ".h": "c", ".cc": "cpp",
    ".cpp": "cpp", ".swift": "swift", ".scala": "scala", ".sh": "shell", ".sql": "sql", ".html": "html", ".css": "css",
    ".scss": "scss",
}
_CONFIG_FORMAT_BY_EXT = {
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".json": "json", ".env": "env", ".ini": "ini", ".cfg": "ini",
    ".conf": "ini", ".properties": "properties", ".jsonc": "json", ".json5": "json",
    # Apps that keep settings in a database seed them from SQL: `INSERT INTO settings ... ('app.concurrency', '10')`.
    # Only `('dotted.key', 'value')` tuples are read, so ordinary SQL files simply yield no keys.
    ".sql": "sql_seed",
}
_MANIFEST_NAMES = {"go.mod": "go", "package.json": "npm", "pyproject.toml": "pypi", "cargo.toml": "cargo", "pom.xml": "maven"}
_REQUIREMENTS = re.compile(r"^requirements[\w.-]*\.txt$", re.IGNORECASE)


@dataclass(slots=True, frozen=True)
class SymbolRecord:
    name: str
    kind: str  # function | class | method | const | type
    path: str
    line: int


@dataclass(slots=True, frozen=True)
class ConfigKeyRecord:
    key: str
    path: str
    value: str | None


@dataclass(slots=True, frozen=True)
class DependencyRecord:
    name: str
    ecosystem: str  # go | npm | pypi | cargo | maven | other
    version: str | None
    path: str


# -- path classification ------------------------------------------------------------------------
def _parts(path: str) -> tuple[list[str], str, str]:
    p = PurePosixPath(path.replace("\\", "/"))
    return [part.lower() for part in p.parts[:-1]], p.name, p.name.lower()


def logical_name(path: str) -> str:
    """`config.toml.sample` -> `config.toml`, `.env.example` -> `.env` (templates share their original format)."""
    name = PurePosixPath(path.replace("\\", "/")).name
    lower = name.lower()
    for suffix in _DERIVED_SUFFIXES:
        if lower.endswith(suffix) and len(lower) > len(suffix):
            return name[: -len(suffix)]
    return name


def _ext(name: str) -> str:
    return PurePosixPath(name).suffix.lower()


def language_of(path: str) -> str | None:
    return _LANG_BY_EXT.get(_ext(logical_name(path)))


def config_format(path: str) -> str | None:
    """`yaml` | `toml` | `json` | `env` | `ini` | `properties` | `dockerfile` | None."""
    name = logical_name(path)
    lower = name.lower()
    if lower == ".env" or lower.startswith(".env."):
        return "env"
    if lower == "dockerfile" or lower.startswith("dockerfile.") or lower.endswith(".dockerfile"):
        return "dockerfile"
    if lower in ("setup.cfg", "tox.ini", ".editorconfig", ".flake8", ".gitconfig"):
        return "ini"
    return _CONFIG_FORMAT_BY_EXT.get(_ext(name))


def manifest_ecosystem(path: str) -> str | None:
    _dirs, name, lower = _parts(path)
    if lower in _MANIFEST_NAMES:
        return _MANIFEST_NAMES[lower]
    if _REQUIREMENTS.match(lower):
        return "pypi"
    return None


def is_config_path(path: str) -> bool:
    return config_format(path) is not None or manifest_ecosystem(path) is not None


def is_doc_path(path: str) -> bool:
    return _ext(path) in _DOC_EXTS


def should_skip(path: str, size: int | None = None) -> bool:
    """Vendored, minified, generated, lock and oversize files carry no decisions worth extracting."""
    dirs, name, lower = _parts(path)
    if size is not None and size > MAX_FILE_BYTES:
        return True
    if any(d in _SKIP_DIR_PARTS for d in dirs):
        return True
    if "/".join(dirs).find("static/vendor") >= 0:
        return True
    return bool(_SKIP_FILE_PATTERNS.search(lower))


def is_noisy_config(path: str) -> bool:
    """Translations, fixtures and schemas: keep the File, skip its keys."""
    dirs, _name, lower = _parts(path)
    if any(d in _NOISY_CONFIG_PARTS for d in dirs):
        return True
    return lower.endswith(".schema.json")


# -- literal values -----------------------------------------------------------------------------
_LITERAL = re.compile(
    r"""^(?P<lit>-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|0x[0-9a-fA-F]+|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`[^`]*`|"""
    r"""true|false|True|False|None|null|nil)\s*(?:[;,]\s*)?(?://.*|#.*)?$"""
)


def literal_value(expr: str) -> str | None:
    """The normalised scalar when `expr` is a bare literal (number, string, bool, null); else None."""
    m = _LITERAL.match(expr.strip())
    if not m:
        return None
    lit = m.group("lit")
    if lit[0] in "\"'`" and lit[-1] == lit[0] and len(lit) >= 2:
        return lit[1:-1][:MAX_VALUE_CHARS]
    return {"True": "true", "False": "false", "None": "null", "nil": "null"}.get(lit, lit)


def normalise_scalar(value: Any) -> str | None:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value) if isinstance(value, float) else str(value)
    if isinstance(value, str):
        return value[:MAX_VALUE_CHARS]
    return None


# -- source symbols -----------------------------------------------------------------------------
_JS_KEYWORDS = {"if", "for", "while", "switch", "catch", "function", "return", "else", "do", "try", "with", "new", "typeof",
                "await", "yield", "constructor", "super", "import", "export", "default", "case"}
_GO_FUNC = re.compile(r"^func\s+(?P<recv>\([^)]*\)\s*)?(?P<name>[A-Za-z_]\w*)\s*[\[(]")
_GO_TYPE = re.compile(r"^type\s+(?P<name>[A-Za-z_]\w*)(?:\[[^\]]*\])?\s+(?P<what>struct|interface|\S+)")
_GO_TYPE_BLOCK = re.compile(r"^\t(?P<name>[A-Za-z_]\w*)\s+(?P<what>struct|interface)\s*\{")
_GO_CONST = re.compile(r"^(?:const\s+)?(?P<name>[A-Za-z_]\w*)\s*(?:[A-Za-z_][\w.]*\s*)?=\s*(?P<value>.+)$")
_PY_DEF = re.compile(r"^(?P<indent>\s*)(?:async\s+)?def\s+(?P<name>[A-Za-z_]\w*)\s*\(")
_PY_CLASS = re.compile(r"^class\s+(?P<name>[A-Za-z_]\w*)")
_PY_CONST = re.compile(r"^(?P<name>[A-Z][A-Z0-9_]+)\s*(?::\s*[\w\[\], |.]+)?\s*=\s*(?P<value>.+)$")
_TS_FUNC = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(?P<name>[A-Za-z_$][\w$]*)")
_TS_CLASS = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)")
_TS_TYPE = re.compile(r"^(?:export\s+)?(?:declare\s+)?(?:interface|type|enum)\s+(?P<name>[A-Za-z_$][\w$]*)")
_TS_VAR = re.compile(r"^(?P<export>export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*(?::\s*[^=]+?)?\s*=\s*(?P<value>.+)$")
_TS_METHOD = re.compile(r"^\s{2,}(?:(?:public|private|protected|static|async|readonly|override)\s+)*(?P<name>[A-Za-z_$][\w$]*)\s*\([^)]*\)\s*(?::\s*[^{]+)?\{\s*$")
_RS_FN = re.compile(r"^(?P<indent>\s*)(?:pub(?:\([^)]*\))?\s+)?(?:const\s+)?(?:async\s+)?(?:unsafe\s+)?(?:extern\s+\"[^\"]*\"\s+)?fn\s+(?P<name>[A-Za-z_]\w*)")
_RS_TYPE = re.compile(r"^(?:pub(?:\([^)]*\))?\s+)?(?P<what>struct|enum|trait|type|union)\s+(?P<name>[A-Za-z_]\w*)")
_RS_CONST = re.compile(r"^(?:pub(?:\([^)]*\))?\s+)?(?:const|static)\s+(?P<name>[A-Z_][A-Z0-9_]*)\s*:\s*[^=]+=\s*(?P<value>.+)$")
_JV_CLASS = re.compile(r"^\s*(?:(?:public|private|protected|abstract|final|static|open|data|sealed|internal|inner)\s+)*(?P<what>class|interface|enum|object|record|annotation class)\s+(?P<name>[A-Za-z_]\w*)")
_JV_METHOD = re.compile(r"^\s+(?:(?:public|private|protected|static|final|synchronized|abstract|native|default)\s+)+(?:<[^>]+>\s*)?[\w<>\[\], ?.]+\s+(?P<name>[a-z]\w*)\s*\([^)]*\)\s*(?:throws[^{]+)?\{")
_KT_FUN = re.compile(r"^(?P<indent>\s*)(?:(?:override|private|public|internal|protected|suspend|open|inline|operator|infix)\s+)*fun\s+(?:<[^>]+>\s+)?(?:[\w<>.]+\.)?(?P<name>[A-Za-z_]\w*)\s*\(")
_JV_CONST = re.compile(r"^\s*(?:(?:public|private|protected)\s+)?(?:static\s+final|final\s+static)\s+[\w<>\[\]]+\s+(?P<name>[A-Z][A-Z0-9_]*)\s*=\s*(?P<value>.+)$")
_KT_CONST = re.compile(r"^\s*(?:(?:private|internal|public)\s+)?(?:const\s+)?val\s+(?P<name>[A-Z][A-Z0-9_]*)\s*(?::\s*\w+)?\s*=\s*(?P<value>.+)$")
_ARROW = re.compile(r"^(?:async\s+)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*(?::\s*[^=]+?)?\s*=>|^(?:async\s+)?function\b")


def _go(lines: list[str]) -> Iterable[tuple[str, str, int, str | None]]:
    in_const, in_type = False, False
    for n, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("const ("):
            in_const = True
            continue
        if stripped.startswith("type ("):
            in_type = True
            continue
        if (in_const or in_type) and stripped == ")":
            in_const = in_type = False
            continue
        if m := _GO_FUNC.match(line):
            yield m.group("name"), "method" if m.group("recv") else "function", n, None
        elif m := _GO_TYPE.match(line):
            yield m.group("name"), "class" if m.group("what") == "struct" else "type", n, None
        elif in_type and (m := _GO_TYPE_BLOCK.match(line)):
            yield m.group("name"), "class" if m.group("what") == "struct" else "type", n, None
        elif (in_const or line.startswith("const ")) and (m := _GO_CONST.match(line[6:] if line.startswith("const ") else line.strip())):
            value = literal_value(m.group("value"))
            if value is not None:
                yield m.group("name"), "const", n, value


def _python(lines: list[str]) -> Iterable[tuple[str, str, int, str | None]]:
    for n, line in enumerate(lines, 1):
        if m := _PY_DEF.match(line):
            yield m.group("name"), "method" if m.group("indent") else "function", n, None
        elif m := _PY_CLASS.match(line):
            yield m.group("name"), "class", n, None
        elif m := _PY_CONST.match(line):
            value = literal_value(m.group("value"))
            if value is not None:
                yield m.group("name"), "const", n, value


def _ts(lines: list[str]) -> Iterable[tuple[str, str, int, str | None]]:
    for n, line in enumerate(lines, 1):
        if m := _TS_FUNC.match(line):
            yield m.group("name"), "function", n, None
        elif m := _TS_CLASS.match(line):
            yield m.group("name"), "class", n, None
        elif m := _TS_TYPE.match(line):
            yield m.group("name"), "type", n, None
        elif m := _TS_VAR.match(line):
            value_expr = m.group("value").strip()
            if _ARROW.match(value_expr):
                yield m.group("name"), "function", n, None
            else:
                value = literal_value(value_expr)
                if value is not None or m.group("export"):
                    yield m.group("name"), "const", n, value
        elif (m := _TS_METHOD.match(line)) and m.group("name") not in _JS_KEYWORDS:
            yield m.group("name"), "method", n, None


def _rust(lines: list[str]) -> Iterable[tuple[str, str, int, str | None]]:
    for n, line in enumerate(lines, 1):
        if m := _RS_FN.match(line):
            yield m.group("name"), "method" if m.group("indent") else "function", n, None
        elif m := _RS_TYPE.match(line):
            yield m.group("name"), "class" if m.group("what") == "struct" else "type", n, None
        elif m := _RS_CONST.match(line):
            value = literal_value(m.group("value"))
            if value is not None:
                yield m.group("name"), "const", n, value


def _java_kotlin(lines: list[str], kotlin: bool) -> Iterable[tuple[str, str, int, str | None]]:
    for n, line in enumerate(lines, 1):
        if m := _JV_CLASS.match(line):
            yield m.group("name"), "class" if m.group("what") in ("class", "record", "object") else "type", n, None
        elif kotlin and (m := _KT_FUN.match(line)):
            yield m.group("name"), "method" if m.group("indent") else "function", n, None
        elif not kotlin and (m := _JV_METHOD.match(line)):
            yield m.group("name"), "method", n, None
        elif m := (_KT_CONST.match(line) if kotlin else _JV_CONST.match(line)):
            value = literal_value(m.group("value"))
            if value is not None:
                yield m.group("name"), "const", n, value


_EXTRACTORS = {
    "go": _go, "python": _python, "typescript": _ts, "javascript": _ts, "vue": _ts, "rust": _rust,
    "java": lambda lines: _java_kotlin(lines, False), "kotlin": lambda lines: _java_kotlin(lines, True),
}


def extract_symbols(path: str, text: str) -> tuple[list[SymbolRecord], list[ConfigKeyRecord]]:
    """Symbols declared in a source file plus the constants with literal values as config keys."""
    lang = language_of(path)
    extractor = _EXTRACTORS.get(lang or "")
    if extractor is None or not text:
        return [], []
    lines = text.splitlines()
    if lang == "vue":  # only the <script> block declares anything
        lines = _vue_script_lines(lines)
    symbols: list[SymbolRecord] = []
    keys: list[ConfigKeyRecord] = []
    seen: set[tuple[str, str]] = set()
    for name, kind, line, value in extractor(lines):
        if (name, kind) in seen:
            continue
        seen.add((name, kind))
        symbols.append(SymbolRecord(name, kind, path, line))
        if kind == "const" and value is not None and len(keys) < MAX_KEYS_PER_FILE:
            keys.append(ConfigKeyRecord(name, path, value))
        if len(symbols) >= MAX_SYMBOLS_PER_FILE:
            break
    return symbols, keys


def _vue_script_lines(lines: list[str]) -> list[str]:
    out, inside = [], False
    for line in lines:
        if line.lstrip().startswith("<script"):
            inside = True
            out.append("")
            continue
        if line.lstrip().startswith("</script"):
            inside = False
        out.append(line if inside else "")
    return out


# -- configuration keys -------------------------------------------------------------------------
def flatten(data: Any, *, max_depth: int = MAX_KEY_DEPTH) -> dict[str, str]:
    """Nested mappings to dotted keys with scalar values; lists of scalars join with `, `; deeper levels and
    lists of mappings are skipped. Insertion order is preserved so `MAX_KEYS_PER_FILE` keeps the top of the file."""
    out: dict[str, str] = {}

    def walk(node: Any, prefix: str, depth: int) -> None:
        if isinstance(node, dict):
            if depth >= max_depth:
                return
            for k, v in node.items():
                key = f"{prefix}.{k}" if prefix else str(k)
                walk(v, key, depth + 1)
        elif isinstance(node, list):
            if prefix and node and all(not isinstance(x, dict | list) for x in node):
                out[prefix] = ", ".join(normalise_scalar(x) or "" for x in node)[:MAX_VALUE_CHARS]
        else:
            scalar = normalise_scalar(node)
            if prefix and scalar is not None:
                out[prefix] = scalar

    walk(data, "", 0)
    return out


_ENV_LINE = re.compile(r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(?P<value>.*)$")
_DOCKER_ENV = re.compile(r"^\s*(?:ENV|ARG)\s+(?P<rest>.+)$", re.IGNORECASE)


def _parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _ENV_LINE.match(line)
        if not m:
            continue
        value = m.group("value").strip()
        quote = value[:1]
        if quote in ("\"", "'") and (end := value.find(quote, 1)) > 0:
            value = value[1:end]
        else:
            value = value.split(" #", 1)[0].strip()
        out[m.group("key")] = value[:MAX_VALUE_CHARS]
    return out


def _parse_dockerfile(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = _DOCKER_ENV.match(line)
        if not m:
            continue
        rest = m.group("rest").strip()
        if "=" in rest:
            for pair in re.findall(r'([A-Za-z_][\w.]*)=("(?:[^"\\]|\\.)*"|\S+)', rest):
                out[pair[0]] = pair[1].strip('"')[:MAX_VALUE_CHARS]
        else:
            parts = rest.split(None, 1)
            if len(parts) == 2:
                out[parts[0]] = parts[1].strip()[:MAX_VALUE_CHARS]
    return out


def _parse_ini(text: str) -> dict[str, str]:
    cp = configparser.ConfigParser(interpolation=None, strict=False, allow_no_value=True, delimiters=("=", ":"))
    cp.optionxform = str  # keep key case
    try:
        cp.read_string(text)
    except configparser.Error:
        return _parse_env(text)
    out: dict[str, str] = {}
    for section in cp.sections():
        for key, value in cp.items(section):
            out[f"{section}.{key}"] = (value or "").strip()[:MAX_VALUE_CHARS]
    for key, value in cp.defaults().items():
        out[key] = (value or "").strip()[:MAX_VALUE_CHARS]
    return out


# ('app.concurrency', '10') / ('privacy.exportable', '["profile", "subscriptions"]'): a dotted key, then a quoted value
_SQL_SEED = re.compile(r"\(\s*'(?P<key>[A-Za-z_][\w-]*(?:\.[\w-]+)+)'\s*,\s*'(?P<value>(?:[^']|'')*)'\s*[,)]")


def _parse_sql_seed(text: str) -> dict[str, str]:
    """Settings seeded from SQL `VALUES` tuples. Values are often JSON-encoded (`'"http://x"'`, `'10'`, `'true'`,
    `'[...]'`); they are decoded to the scalar a reader would recognise. Later tuples for a key win, as in SQL."""
    out: dict[str, str] = {}
    for m in _SQL_SEED.finditer(text):
        raw = m.group("value").replace("''", "'")
        try:
            parsed: Any = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            parsed = raw
        if isinstance(parsed, list):
            if not all(not isinstance(x, dict | list) for x in parsed):
                continue
            value = ", ".join(normalise_scalar(x) or "" for x in parsed)[:MAX_VALUE_CHARS]
        elif isinstance(parsed, dict):
            continue
        else:
            value = normalise_scalar(parsed)
        if value is not None:
            out[m.group("key")] = value
    return out


def _strip_json_comments(text: str) -> str:
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    return re.sub(r",(\s*[}\]])", r"\1", text)


def parse_config(path: str, text: str) -> dict[str, str]:
    """Dotted key -> scalar value for a configuration file; `{}` when the file is not config or does not parse."""
    fmt = config_format(path)
    if fmt is None or not text or not text.strip():
        return {}
    try:
        if fmt == "yaml":
            docs = [d for d in yaml.safe_load_all(text) if d is not None]
            data: Any = docs[0] if len(docs) == 1 else {str(i): d for i, d in enumerate(docs)} if docs else {}
        elif fmt == "toml":
            data = tomllib.loads(text)
        elif fmt == "json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = json.loads(_strip_json_comments(text))
        elif fmt == "env":
            return dict(list(_parse_env(text).items())[:MAX_KEYS_PER_FILE])
        elif fmt == "dockerfile":
            return dict(list(_parse_dockerfile(text).items())[:MAX_KEYS_PER_FILE])
        elif fmt == "properties":
            return dict(list(_parse_env(text).items())[:MAX_KEYS_PER_FILE])
        elif fmt == "sql_seed":
            return dict(list(_parse_sql_seed(text).items())[:MAX_KEYS_PER_FILE])
        else:
            return dict(list(_parse_ini(text).items())[:MAX_KEYS_PER_FILE])
    except (yaml.YAMLError, tomllib.TOMLDecodeError, json.JSONDecodeError, ValueError, TypeError, RecursionError) as exc:
        log.debug("config %s does not parse: %s", path, str(exc)[:120])
        return {}
    if not isinstance(data, dict):
        return {}
    return dict(list(flatten(data).items())[:MAX_KEYS_PER_FILE])


def extract_config_keys(path: str, text: str) -> list[ConfigKeyRecord]:
    if is_noisy_config(path):
        return []
    return [ConfigKeyRecord(k, path, v) for k, v in parse_config(path, text).items()]


# -- dependencies --------------------------------------------------------------------------------
_GO_REQUIRE = re.compile(r"^\s*(?:require\s+)?(?P<name>[\w.\-/~]+)\s+(?P<version>v[\w.\-+]+)(?P<indirect>\s*//\s*indirect)?\s*$")
_PEP508 = re.compile(r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(?P<spec>[^;#]*)")
_POM_DEP = re.compile(r"<dependency>(.*?)</dependency>", re.S)
_POM_FIELD = re.compile(r"<(groupId|artifactId|version)>\s*([^<]+?)\s*</\1>")


def _go_mod(text: str) -> Iterable[tuple[str, str | None]]:
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_block = True
            continue
        if in_block and stripped == ")":
            in_block = False
            continue
        if not (in_block or stripped.startswith("require ")):
            continue
        m = _GO_REQUIRE.match(stripped)
        if m and not m.group("indirect"):
            yield m.group("name"), m.group("version")


def _package_json(text: str) -> Iterable[tuple[str, str | None]]:
    data = json.loads(text)
    if not isinstance(data, dict):
        return
    for section in ("dependencies", "devDependencies"):
        deps = data.get(section) or {}
        if isinstance(deps, dict):
            for name, version in deps.items():
                yield str(name), normalise_scalar(version)


def _requirements(text: str) -> Iterable[tuple[str, str | None]]:
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "git+", "http")):
            continue
        m = _PEP508.match(line)
        if m:
            spec = m.group("spec").strip() or None
            yield m.group("name"), spec


def _pep508_list(items: Any) -> Iterable[tuple[str, str | None]]:
    for item in items or []:
        if isinstance(item, str):
            m = _PEP508.match(item)
            if m:
                yield m.group("name"), (m.group("spec").strip() or None)


def _pyproject(text: str) -> Iterable[tuple[str, str | None]]:
    data = tomllib.loads(text)
    project = data.get("project") or {}
    yield from _pep508_list(project.get("dependencies"))
    for extra in (project.get("optional-dependencies") or {}).values():
        yield from _pep508_list(extra)
    for group in (data.get("dependency-groups") or {}).values():
        yield from _pep508_list([g for g in group if isinstance(g, str)])
    poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
    for name, spec in poetry.items():
        if name.lower() == "python":
            continue
        yield name, normalise_scalar(spec) if not isinstance(spec, dict) else normalise_scalar(spec.get("version"))


def _cargo(text: str) -> Iterable[tuple[str, str | None]]:
    data = tomllib.loads(text)
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        for name, spec in (data.get(section) or {}).items():
            yield name, normalise_scalar(spec) if not isinstance(spec, dict) else normalise_scalar(spec.get("version"))


def _pom(text: str) -> Iterable[tuple[str, str | None]]:
    for block in _POM_DEP.findall(text):
        fields = dict(_POM_FIELD.findall(block))
        if "artifactId" in fields:
            name = f"{fields.get('groupId', '')}:{fields['artifactId']}".strip(":")
            yield name, fields.get("version")


def parse_dependencies(path: str, text: str) -> list[DependencyRecord]:
    """Declared (direct) dependencies of a manifest; `[]` for any other path or an unparsable manifest."""
    eco = manifest_ecosystem(path)
    if eco is None or not text:
        return []
    name = logical_name(path).lower()
    reader = {
        "go.mod": _go_mod, "package.json": _package_json, "pyproject.toml": _pyproject, "cargo.toml": _cargo, "pom.xml": _pom,
    }.get(name, _requirements if eco == "pypi" else None)
    if reader is None:
        return []
    try:
        pairs = list(reader(text))
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, ValueError, TypeError, AttributeError) as exc:
        log.debug("manifest %s does not parse: %s", path, str(exc)[:120])
        return []
    seen: dict[str, DependencyRecord] = {}
    for dep_name, version in pairs:
        if dep_name and dep_name.lower() not in seen:
            seen[dep_name.lower()] = DependencyRecord(dep_name, eco, version, path)
    return list(seen.values())


def languages(paths: Iterable[str], top: int = 5) -> list[str]:
    counts: dict[str, int] = {}
    for p in paths:
        lang = language_of(p)
        if lang and not should_skip(p):
            counts[lang] = counts.get(lang, 0) + 1
    return [lang for lang, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:top]]


__all__ = [
    "ConfigKeyRecord", "DependencyRecord", "SymbolRecord", "config_format", "extract_config_keys", "extract_symbols",
    "flatten", "is_config_path", "is_doc_path", "is_noisy_config", "language_of", "languages", "literal_value",
    "logical_name", "manifest_ecosystem", "parse_config", "parse_dependencies", "should_skip",
]
