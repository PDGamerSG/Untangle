"""Design documents: ADRs (status, date, Context/Decision/Consequences), changelogs, READMEs and `docs/**/*.md`.

ADRs are the strongest decision signal a repository has, so every ADR becomes a Decision row (kind `adr`) with
its status as the object; "Superseded by ADR-0007" links the two documents and the two decisions."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import PurePosixPath

from kyun import ids
from kyun.ingest.decisions import DecisionRow, make_decision
from kyun.ingest.symbols import is_doc_path, should_skip

log = logging.getLogger("kyun.ingest.docs")

MAX_DOCS = 300
MAX_DOC_CHARS = 40_000
MAX_RATIONALE_CHARS = 2000

_ADR_DIRS = ("docs/adr", "docs/adrs", "docs/decisions", "docs/decision-records", "adr", "adrs", "doc/adr", "doc/adrs",
             "docs/architecture/decisions", "docs/architecture/adr", "architecture/decisions", "decisions")
_ADR_FILE = re.compile(r"^(?:adr[-_]?)?(\d{3,5})[-_].*\.(md|markdown|rst)$", re.IGNORECASE)
_ADR_NUMBER_IN_TITLE = re.compile(r"^(?:adr[-\s_]*)?(\d{1,5})[.:\-\s]+", re.IGNORECASE)
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_RST_TITLE = re.compile(r"^(.+)\n[=\-~]{3,}\s*$", re.MULTILINE)
_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_STATUS_LINE = re.compile(r"^\s*\**status\**\s*[:：]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_DATE_LINE = re.compile(r"^\s*\**date\**\s*[:：]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_SUPERSEDED_BY = re.compile(r"superseded\s+by\s*:?\s*(?:\[([^\]]*)\]\(([^)]+)\))?\s*(?:adr[-\s_]*)?(\d{1,5})?", re.IGNORECASE)
_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%Y-%m", "%Y")
_PATH_MENTION = re.compile(r"(?<![\w/])((?:[\w.-]+/)+[\w.-]+\.(?:go|py|ts|tsx|js|jsx|vue|rs|java|kt|yaml|yml|toml|json|md|sql|env))\b")
_STATUSES = ("accepted", "proposed", "deprecated", "superseded", "rejected", "draft", "approved", "pending", "obsolete")


@dataclass(slots=True)
class DocumentRecord:
    path: str
    title: str
    kind: str  # adr | design | changelog | readme | doc
    text: str
    status: str | None = None
    adr_number: int | None = None
    date: int | None = None
    superseded_by_ref: str | None = None  # link target or ADR number as written
    superseded_by_path: str | None = None  # resolved later
    sections: list[tuple[str, str]] = field(default_factory=list)
    context: str | None = None
    decision: str | None = None
    consequences: str | None = None


# -- selection -------------------------------------------------------------------------------------
def is_adr_path(path: str) -> bool:
    p = PurePosixPath(path.replace("\\", "/"))
    parent = str(p.parent).lower().lstrip("./")
    if any(parent == d or parent.startswith(d + "/") for d in _ADR_DIRS):
        return bool(re.search(r"\.(md|markdown|rst)$", p.name, re.IGNORECASE)) and not p.name.lower().startswith(("readme", "template", "index"))
    return bool(_ADR_FILE.match(p.name)) and p.name.lower() not in ("0000-template.md",)


def doc_kind(path: str) -> str:
    name = PurePosixPath(path).name.lower()
    lower = path.lower()
    if is_adr_path(path):
        return "adr"
    if name.startswith(("changelog", "changes", "history", "release", "releases")):
        return "changelog"
    if name.startswith("readme"):
        return "readme"
    if re.search(r"(design|rfc|architecture|proposal|spec)", lower):
        return "design"
    return "doc"


def select_doc_paths(paths: Iterable[str], max_docs: int = MAX_DOCS) -> list[str]:
    """ADRs, changelogs, READMEs, top-level markdown and `docs/**` / `doc/**` markdown, best first."""
    chosen: list[tuple[int, str]] = []
    for path in paths:
        if not is_doc_path(path) or should_skip(path):
            continue
        p = PurePosixPath(path.replace("\\", "/"))
        kind = doc_kind(path)
        top_level = len(p.parts) == 1
        in_docs = p.parts and p.parts[0].lower() in ("docs", "doc", "documentation", "design", "rfcs", "adr", "adrs", "decisions")
        if kind == "adr":
            rank = 0
        elif kind == "changelog" and len(p.parts) <= 2:
            rank = 1
        elif kind == "readme" and len(p.parts) <= 2:
            rank = 2
        elif top_level and p.suffix.lower() in (".md", ".rst"):
            rank = 3
        elif in_docs and p.suffix.lower() in (".md", ".rst", ".mdx"):
            rank = 4 if kind == "design" else 5
        elif kind == "readme":
            rank = 6
        else:
            continue
        chosen.append((rank, path))
    chosen.sort(key=lambda t: (t[0], t[1]))
    return [p for _, p in chosen[:max_docs]]


# -- parsing ----------------------------------------------------------------------------------------
def _front_matter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONT_MATTER.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip().strip("'\"")
    return meta, text[m.end():]


def split_sections(text: str) -> list[tuple[str, str]]:
    """`(heading, body)` pairs; the text before the first heading has heading ''."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else _HEADING.match(line)
        if m:
            sections.append((m.group(2).strip(), []))
        else:
            sections[-1][1].append(line)
    out = [(h, "\n".join(body).strip()) for h, body in sections]
    return [(h, b) for h, b in out if h or b]


def parse_date(value: str | None) -> int | None:
    if not value:
        return None
    value = value.strip().strip("*_ ").split(" (")[0]
    for fmt in _DATE_FORMATS:
        try:
            return int(datetime.strptime(value[: len(fmt) + 12 if "%B" in fmt else len(value)], fmt).replace(tzinfo=UTC).timestamp() * 1000)
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        try:
            return int(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=UTC).timestamp() * 1000)
        except ValueError:
            return None
    return None


def canonical_status(raw: str | None) -> str | None:
    if not raw:
        return None
    lower = raw.lower()
    if "supersed" in lower:
        return "superseded"
    for s in _STATUSES:
        if s in lower:
            return {"approved": "accepted", "obsolete": "deprecated"}.get(s, s)
    return lower.strip("*_ ")[:40] or None


def _section(sections: list[tuple[str, str]], *names: str) -> str | None:
    for heading, body in sections:
        h = heading.lower().strip()
        if any(h == n or h.startswith(n + " ") or h.startswith(n + ":") for n in names):
            return body or None
    return None


def parse_document(path: str, text: str) -> DocumentRecord:
    text = (text or "")[:MAX_DOC_CHARS]
    meta, body = _front_matter(text)
    sections = split_sections(body)
    kind = doc_kind(path)
    title = meta.get("title") or next((h for h, _ in sections if h), None)
    if not title and path.lower().endswith(".rst"):
        m = _RST_TITLE.search(body)
        title = m.group(1).strip() if m else None
    if not title:
        title = PurePosixPath(path).stem.replace("-", " ").replace("_", " ")
    doc = DocumentRecord(path=path, title=title.strip()[:300], kind=kind, text=text, sections=sections)
    if kind != "adr":
        return doc
    m = _ADR_FILE.match(PurePosixPath(path).name)
    if m:
        doc.adr_number = int(m.group(1))
    else:
        t = _ADR_NUMBER_IN_TITLE.match(doc.title)
        doc.adr_number = int(t.group(1)) if t else None
    doc.title = _ADR_NUMBER_IN_TITLE.sub("", doc.title, count=1).strip() or doc.title
    status_raw = meta.get("status") or _section(sections, "status") or (lambda s: s.group(1) if s else None)(_STATUS_LINE.search(body))
    if status_raw:
        status_raw = status_raw.strip().splitlines()[0].strip()
    doc.status = canonical_status(status_raw)
    if status_raw:
        sup = _SUPERSEDED_BY.search(status_raw)
        if sup and (sup.group(2) or sup.group(3)):
            doc.superseded_by_ref = sup.group(2) or sup.group(3)
    doc.date = parse_date(meta.get("date") or _section(sections, "date") or (lambda s: s.group(1) if s else None)(_DATE_LINE.search(body)))
    doc.context = _section(sections, "context", "context and problem statement", "problem", "background")
    doc.decision = _section(sections, "decision", "decision outcome", "resolution", "proposal")
    doc.consequences = _section(sections, "consequences", "positive consequences", "implications")
    return doc


def resolve_supersessions(docs: list[DocumentRecord]) -> None:
    """Turn `superseded_by_ref` (a relative link or an ADR number) into `superseded_by_path`."""
    by_path = {d.path: d for d in docs}
    by_number: dict[int, list[DocumentRecord]] = {}
    for d in docs:
        if d.kind == "adr" and d.adr_number is not None:
            by_number.setdefault(d.adr_number, []).append(d)
    for d in docs:
        ref = d.superseded_by_ref
        if not ref:
            continue
        target = None
        if ref.isdigit():
            same_dir = [c for c in by_number.get(int(ref), []) if PurePosixPath(c.path).parent == PurePosixPath(d.path).parent]
            target = (same_dir or by_number.get(int(ref)) or [None])[0]
        else:
            rel = ref.split("#", 1)[0].strip()
            candidate = str(PurePosixPath(d.path).parent / rel) if not rel.startswith("/") else rel.lstrip("/")
            candidate = _normalise(candidate)
            target = by_path.get(candidate)
            if target is None:
                name = PurePosixPath(rel).name.lower()
                target = next((c for c in docs if PurePosixPath(c.path).name.lower() == name), None)
        if target is not None and target.path != d.path:
            d.superseded_by_path = target.path


def _normalise(path: str) -> str:
    parts: list[str] = []
    for part in path.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:80] or "untitled"


# -- decisions --------------------------------------------------------------------------------------
def adr_decisions(
    repo: str,
    docs: list[DocumentRecord],
    *,
    added_at: dict[str, int] | None = None,
    added_by: dict[str, str] | None = None,
    known_paths: set[str] | None = None,
) -> list[DecisionRow]:
    """One `adr` decision per ADR document; `added_at`/`added_by` map a path to the commit time and author
    person id of the commit that introduced the file (used when the ADR has no Date)."""
    added_at = added_at or {}
    added_by = added_by or {}
    known_paths = known_paths or set()
    rows: dict[str, DecisionRow] = {}
    for d in docs:
        if d.kind != "adr":
            continue
        status = d.status or "accepted"
        key = f"adr|{slug(d.title)}|adr_status"
        number = f"ADR-{d.adr_number:04d}" if d.adr_number is not None else "ADR"
        rationale = " ".join(x for x in (d.decision, d.context) if x)
        row = make_decision(
            repo, "adr", key, d.path,
            subject=d.title, predicate="adr_status", object=status,
            text=f"{number} \"{d.title}\" is {status}" + (f" (superseded by {d.superseded_by_path})" if d.superseded_by_path else ""),
            rationale=re.sub(r"\s+", " ", rationale)[:MAX_RATIONALE_CHARS] or None,
            valid_from=d.date or added_at.get(d.path) or 0, confidence=0.95, signal="adr_status",
        )
        row.link("DECIDED_IN", ids.document_id(repo, d.path))
        row.link("EVIDENCED_BY", ids.document_id(repo, d.path))
        row.link("ABOUT", ids.file_id(repo, d.path))
        for mentioned in dict.fromkeys(_PATH_MENTION.findall(d.text)):
            if mentioned in known_paths:
                row.link("ABOUT", ids.file_id(repo, mentioned))
        if d.path in added_by:
            row.link("STATED_BY", added_by[d.path])
        rows[d.path] = row
    for d in docs:
        if d.kind == "adr" and d.superseded_by_path and d.superseded_by_path in rows and d.path in rows:
            newer, older = rows[d.superseded_by_path], rows[d.path]
            newer.link("SUPERSEDES", older.id, signal="adr_status", at=newer.valid_from or older.valid_from)
    return list(rows.values())


__all__ = [
    "DocumentRecord", "adr_decisions", "canonical_status", "doc_kind", "is_adr_path", "parse_date", "parse_document",
    "resolve_supersessions", "select_doc_paths", "slug", "split_sections",
]
