"""Pre-flight check: before a change is made, show what the repository's history says about it.

Input is a description of the change, a unified diff, or both, plus optional file paths. The check is deterministic
(no model call) and every finding points at graph evidence:

- **Targets**: the indexed files the change names, and the configuration keys and dependencies whose lines it
  edits or removes (matched by name inside the changed lines of each file), or that the description names.
- **Replaced values coming back**: a proposed value equal to one a later decision replaced, with the reason it was
  replaced. This is the case history is best at catching and reviewers are worst at remembering.
- **Decisions to read first**: active decisions about the targets, with what guards them (an incident, a linked
  issue, a recorded reason, a handover statement, earlier values it replaced).
- **Reach**: files that import the targets (up to three hops through the static import index), code areas whose
  entry points reach them, tests among those files, and files that historically changed in the same commits.
- **Upstream advisories**: for an edited dependency version, public advisories (OSV.dev) that affect the proposed
  version but not the current one.
- **People**: who has the most relevant history on the targets (34_person_to_ask).

The review level is the sum of listed reasons with fixed points, so a reader can see exactly why it is high.
A low level is never a safety guarantee: missing history and dynamic calls are invisible to the graph."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from untangle import advisories as osv
from untangle.answer.models import CypherCall, DecisionCard, PersonCard, Ref
from untangle.answer.retrieve import Recorder, Version, build_dossiers, person_from_row, version_from_row
from untangle.answer.router import MATCH_THRESHOLD, STOPWORDS, match_strength, resolve_entities, route, scrub_repo_terms
from untangle.answer.text import fmt_date, label_of
from untangle.config import settings
from untangle.graph.db import Graph

log = logging.getLogger("untangle.preflight")

MAX_CHANGE_CHARS = 60_000
MAX_PATHS = 50
MAX_HOPS = 3
MAX_REACHED = 300
COCHANGE_MAX_FILES = 40
TIMEOUT_MS = 6000

ChangeKind = Literal["edit", "add", "remove", "delete", "file", "mention"]
Level = Literal["low", "medium", "high"]


# ------------------------------------------------------------------------------------------------------------------
# response models


class Target(BaseModel):
    id: str
    label: str
    name: str | None = None
    path: str | None = None
    key: str | None = None
    current: str | None = None
    proposed: str | None = None
    change: ChangeKind = "file"
    source: Literal["diff", "paths", "text"] = "diff"
    note: str | None = None


class Revival(BaseModel):
    target: str
    proposed: str
    replaced: DecisionCard
    replaced_by: DecisionCard
    reason: str | None = None
    evidence: Ref | None = None


class GuardedDecision(BaseModel):
    decision: DecisionCard
    guards: list[str] = Field(default_factory=list)
    earlier_values: int = 0
    strength: int = 0


class Reached(BaseModel):
    path: str
    hop: int
    via: list[str] = Field(default_factory=list)  # import chain from this file down to the changed file


class Area(BaseModel):
    name: str
    source: str | None = None
    via: list[str] = Field(default_factory=list)


class CoChange(BaseModel):
    path: str
    together: int
    total: int
    share: float


class Reach(BaseModel):
    imports_indexed: bool
    reached: list[Reached] = Field(default_factory=list)
    areas: list[Area] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    cochanged: list[CoChange] = Field(default_factory=list)
    truncated: bool = False


class AdvisoryHit(BaseModel):
    package: str
    ecosystem: str
    version: str
    exact: bool
    current: str | None = None
    advisory: dict[str, Any]


class Advisories(BaseModel):
    checked: bool = True
    note: str | None = None
    introduced: list[AdvisoryHit] = Field(default_factory=list)
    fixed: list[AdvisoryHit] = Field(default_factory=list)


class Reason(BaseModel):
    points: int
    text: str


class Review(BaseModel):
    level: Level
    score: int
    reasons: list[Reason] = Field(default_factory=list)


class Step(BaseModel):
    text: str
    href: str | None = None


class PreflightResponse(BaseModel):
    repo: str
    review: Review
    targets: list[Target] = Field(default_factory=list)
    unresolved_paths: list[str] = Field(default_factory=list)
    revivals: list[Revival] = Field(default_factory=list)
    decisions: list[GuardedDecision] = Field(default_factory=list)
    other_decisions: int = 0
    reach: Reach
    advisories: Advisories = Field(default_factory=Advisories)
    people: list[PersonCard] = Field(default_factory=list)
    next_steps: list[Step] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)
    cypher: list[CypherCall] = Field(default_factory=list)
    ms: float | None = None


class PreflightRequest(BaseModel):
    repo: str = Field(min_length=3, max_length=200)
    change: str = Field(default="", max_length=MAX_CHANGE_CHARS)
    paths: list[str] = Field(default_factory=list, max_length=MAX_PATHS)


# ------------------------------------------------------------------------------------------------------------------
# parsing a change


@dataclass
class FileChange:
    path: str
    status: Literal["modified", "added", "deleted", "named"] = "modified"
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


@dataclass
class ParsedChange:
    files: dict[str, FileChange]
    prose: str
    is_diff: bool


_DIFF_GIT = re.compile(r"^diff --git a/(.+?) b/(.+)$")
_HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")
_META = ("index ", "new file mode", "deleted file mode", "similarity index", "rename from", "rename to", "old mode",
         "new mode", "Binary files", "copy from", "copy to", "dissimilarity index")


def _strip_side(value: str) -> str:
    value = value.split("\t", 1)[0].strip()
    if value.startswith(("a/", "b/")):
        value = value[2:]
    return value


def _clean_path(value: str) -> str:
    return value.strip().strip("`'\"").lstrip("./").strip()


def parse_change(text: str, paths: list[str] | None = None) -> ParsedChange:
    """Split `text` into per-file diff lines and free prose. Hunk line counts decide where a hunk ends, so a removed
    line that starts with `-- ` is never mistaken for a file header."""
    files: dict[str, FileChange] = {}
    prose: list[str] = []
    current: FileChange | None = None
    old_path: str | None = None
    old_left = new_left = 0
    is_diff = False

    def touch(path: str) -> FileChange:
        path = _clean_path(path)
        if path not in files:
            files[path] = FileChange(path=path)
        return files[path]

    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip("\r")
        if current is not None and (old_left > 0 or new_left > 0):
            if line.startswith("+"):
                current.added.append(line[1:])
                new_left -= 1
                continue
            if line.startswith("-"):
                current.removed.append(line[1:])
                old_left -= 1
                continue
            if line.startswith("\\"):
                continue
            if line.startswith(" ") or line == "":
                old_left -= 1
                new_left -= 1
                continue
            old_left = new_left = 0  # malformed hunk: fall through and read the line normally
        match = _DIFF_GIT.match(line)
        if match:
            is_diff = True
            current = touch(match.group(2))
            old_path = None
            continue
        if line.startswith("--- ") and not line.startswith("--- --"):
            old_path = _strip_side(line[4:])
            is_diff = True
            continue
        if line.startswith("+++ ") and old_path is not None:
            new = _strip_side(line[4:])
            if new == "/dev/null":
                current = touch(old_path)
                current.status = "deleted"
            else:
                current = touch(new)
                if old_path == "/dev/null":
                    current.status = "added"
            old_path = None
            continue
        hunk = _HUNK.match(line)
        if hunk and current is not None:
            old_left = int(hunk.group(1)) if hunk.group(1) is not None else 1
            new_left = int(hunk.group(2)) if hunk.group(2) is not None else 1
            continue
        if current is not None and line.startswith(_META):
            if line.startswith("new file mode"):
                current.status = "added"
            elif line.startswith("deleted file mode"):
                current.status = "deleted"
            continue
        prose.append(line)
    for path in paths or []:
        cleaned = _clean_path(path)
        if cleaned and cleaned not in files:
            files[cleaned] = FileChange(path=cleaned, status="named")
    return ParsedChange(files=files, prose="\n".join(prose).strip(), is_diff=is_diff)


def _value(text: str) -> str | None:
    value = re.split(r"\s+(?:#|//)", text.strip(), maxsplit=1)[0].strip().rstrip(",;").strip()
    value = value.strip("\"'`").strip()
    if value.startswith("=") and not value.startswith("=="):
        value = value[1:].strip()
    return value[:120] or None


def assignment(lines: list[str], name: str) -> str | None:
    """The value assigned to `name` on the last of `lines` that sets it (`name = 10`, `"name": "^1.2.0"`, `name: x`,
    `name==1.0`, `name v1.2.3`), or None when no line sets it."""
    pattern = re.compile(
        r"(?:^|[\s\"'{,\[(])" + re.escape(name) + r"[\"']?\s*(==|>=|<=|~=|!=|[:=]|\s)\s*(.+)$", re.IGNORECASE
    )
    found = None
    for line in lines:
        match = pattern.search(line)
        if match:
            op, rest = match.group(1), match.group(2)
            value = _value(rest)
            if value and op in ("==", ">=", "<=", "~=", "!="):
                value = (op if op != "==" else "") + value
            if value:
                found = value
    return found


def mentions(lines: list[str], name: str) -> bool:
    pattern = re.compile(r"(?:^|[^\w.-])" + re.escape(name) + r"(?:$|[^\w-])", re.IGNORECASE)
    return any(pattern.search(line) for line in lines)


def prose_value(text: str, name: str) -> str | None:
    """`set app.concurrency back to 5` -> `5`; `downgrade mocha to 2.0.0` -> `2.0.0`."""
    match = re.search(
        re.escape(name) + r"[^.\n]{0,48}?\b(?:to|=|as|at)\s+[\"'`]?([\w.^~*<>=-]+?)[\"'`]?(?:[\s,;)]|\.(?:\s|$)|$)",
        text, re.IGNORECASE,
    )
    if not match:
        return None
    value = match.group(1).rstrip(".")
    return value or None


def _norm(value: str | None) -> str:
    v = (value or "").strip().strip("\"'`").lower()
    return re.sub(r"^(?:\^|~|==|=|v(?=\d))", "", v).strip()


_TEST = re.compile(r"(^|/)(tests?|__tests__|spec|specs)/|(^|/)test_[^/]+\.py$|_test\.(go|py|rb)$|\.(test|spec)\.[cm]?[jt]sx?$")


def is_test(path: str) -> bool:
    return bool(_TEST.search(path))


# ------------------------------------------------------------------------------------------------------------------
# the check


def preflight(
    repo: str, change: str, *, paths: list[str] | None = None, graph: Graph | None = None, now_ms: int | None = None,
    http: Any = None,
) -> PreflightResponse:
    from untangle.answer import service

    started = time.perf_counter()
    if not change.strip() and not paths:
        raise ValueError("Describe the change, paste a diff, or name at least one file.")
    graph = graph or service.get_graph()
    now_ms = now_ms or int(time.time() * 1000)
    rec = Recorder(graph, timeout_ms=TIMEOUT_MS)
    repo_rows = rec.run("preflight_repo", {"repo": repo})
    if not repo_rows:
        raise service.NotFound(f"Repository {repo} has not been ingested.")
    imports_indexed = bool(repo_rows[0].get("imports_indexed"))

    parsed = parse_change(change[:MAX_CHANGE_CHARS], paths)
    named = list(parsed.files)[:MAX_PATHS]
    file_rows = rec.run("preflight_targets", {"repo": repo, "paths": named}) if named else []
    found_paths = {r["path"] for r in file_rows}
    unresolved = [p for p in named if p not in found_paths]

    targets: list[Target] = []
    seen: set[str] = set()

    def add(target: Target) -> None:
        if target.id not in seen:
            seen.add(target.id)
            targets.append(target)

    def file_target(row: dict[str, Any], fc: FileChange | None, source: str) -> None:
        status = fc.status if fc else "named"
        kind: ChangeKind = {"modified": "edit", "added": "add", "deleted": "delete"}.get(status, "file")  # type: ignore[assignment]
        note = None if row.get("alive", True) else "This path no longer exists at the indexed snapshot."
        add(Target(id=row["id"], label="File", name=row["path"].rsplit("/", 1)[-1], path=row["path"], change=kind,
                   source=source, note=note))  # type: ignore[arg-type]
        if not fc or not (fc.added or fc.removed):
            return
        changed = fc.added + fc.removed
        dep_names = {d["name"].lower() for d in row.get("deps") or [] if d and d.get("name")}
        candidates: list[tuple[str, str, dict[str, Any], str]] = []
        leaf_counts: dict[str, int] = {}
        for k in row.get("keys") or []:
            if k and k.get("key"):
                leaf = k["key"].rsplit(".", 1)[-1]
                leaf_counts[leaf] = leaf_counts.get(leaf, 0) + 1
        for k in row.get("keys") or []:
            if not k or not k.get("key"):
                continue
            key = k["key"]
            if "." in key and key.rsplit(".", 1)[-1].lower() in dep_names:
                continue  # `dependencies.cookie` in a manifest is the cookie dependency, reported once below
            # Prefer the full dotted key (`app.concurrency = 5`); nested formats only show the leaf (`concurrency: 5`).
            probe = key if mentions(changed, key) else key.rsplit(".", 1)[-1]
            candidates.append(("ConfigKey", key, k, probe))
        for d in row.get("deps") or []:
            if d and d.get("name"):
                candidates.append(("Dependency", d["name"], d, d["name"]))
        matched = 0
        for label, name, node, probe in candidates:
            in_added = mentions(fc.added, probe)
            in_removed = mentions(fc.removed, probe)
            if not (in_added or in_removed):
                continue
            proposed = assignment(fc.added, probe) if in_added else None
            current = node.get("current_value") if label == "ConfigKey" else node.get("current_version")
            if in_added and proposed is not None and _norm(proposed) == _norm(current) and in_removed is False:
                continue  # a context-like line that restates the current value
            if in_added and proposed is None and not in_removed:
                continue  # named in a new line without a value: probably a comment or an unrelated identifier
            change_kind: ChangeKind = "edit" if in_added else "remove"
            note = None
            leaf = name.rsplit(".", 1)[-1]
            if label == "ConfigKey" and probe == leaf and leaf_counts.get(leaf, 0) > 1:
                note = f"Matched by the name `{leaf}`, which more than one key in this file uses."
            add(Target(id=node["id"], label=label, name=name, path=row["path"], key=name if label == "ConfigKey" else None,
                       current=current, proposed=proposed, change=change_kind, source="diff", note=note))
            matched += 1
            if matched >= 25:
                break

    for row in file_rows:
        fc = parsed.files.get(row["path"])
        file_target(row, fc, "paths" if fc is None or fc.status == "named" else "diff")

    prose = parsed.prose[:2000]
    terms: list[str] = []
    if prose:
        decision = scrub_repo_terms(route(prose), repo)
        terms = [t.lower() for t in decision.terms][:12]
        resolved = _resolve_prose(rec, repo, decision, prose)
        prose_files = [e.path for e in resolved if e.label == "File" and e.path and e.path not in found_paths]
        if prose_files:
            for row in rec.run("preflight_targets", {"repo": repo, "paths": prose_files}):
                found_paths.add(row["path"])
                file_target(row, None, "text")
        for e in resolved:
            if e.label == "File" or e.id in seen:
                continue
            current = e.extra.get("current_value") if e.label == "ConfigKey" else e.extra.get("current_version")
            probe = e.key or e.name or ""
            proposed = prose_value(prose, probe) if probe else None
            if proposed is None and e.key and "." in e.key:
                proposed = prose_value(prose, e.key.rsplit(".", 1)[-1])
            add(Target(id=e.id, label=e.label, name=e.name, path=e.path, key=e.key, current=current, proposed=proposed,
                       change="mention", source="text"))

    if not targets:
        reach = Reach(imports_indexed=imports_indexed)
        return PreflightResponse(
            repo=repo, review=Review(level="low", score=0, reasons=[]), unresolved_paths=unresolved, reach=reach,
            limits=_limits(imports_indexed, unresolved, nothing=True), cypher=rec.calls,
            next_steps=[Step(text="Name a file path, a configuration key or a dependency, or paste a unified diff, so the check has something in the graph to read.")],
            ms=round((time.perf_counter() - started) * 1000, 1),
        )

    # -- decisions ------------------------------------------------------------------------------------------------
    target_ids = {t.id for t in targets}
    precise = [t.id for t in targets if t.label != "File"]
    files = [t.id for t in targets if t.label == "File"]
    versions: dict[str, Version] = {}
    other_roots: set[str] = set()
    if precise:
        for row in rec.run("decisions_about", {"repo": repo, "ids": precise, "limit": 24, "chain_limit": 160, "terms": terms}):
            versions.setdefault(row["id"], version_from_row(row))
    if files:
        # In a file where the change edits named keys or dependencies, file-level decisions count only when they
        # name one of them; elsewhere every decision about the file is in scope.
        named_in: dict[str, list[str]] = {}
        for t in targets:
            if t.label != "File" and t.source == "diff" and t.path:
                named_in.setdefault(t.path, []).append((t.key or t.name or "").rsplit(".", 1)[-1].lower())
        for row in rec.run("decisions_about", {"repo": repo, "ids": files, "limit": 40, "chain_limit": 200, "terms": terms}):
            v = version_from_row(row)
            children = {a.get("id") for a in v.about if set(a.get("labels") or []) & {"ConfigKey", "Dependency", "Symbol"}}
            if children and not (children & target_ids):
                other_roots.add(v.key or v.id)
                continue
            if not children and v.id not in versions:
                paths_about = {a.get("path") for a in v.about if a.get("path")}
                names = [n for p in paths_about for n in named_in.get(p, []) if n]
                words = f"{v.text or ''} {v.subject or ''} {v.object or ''}".lower()
                if names and not any(re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", words) for n in names):
                    other_roots.add(v.key or v.id)
                    continue
            versions.setdefault(v.id, v)
    dossiers = build_dossiers(versions)
    by_target: dict[str, list[Version]] = {}
    for v in versions.values():
        for a in v.about:
            if a.get("id") in target_ids:
                by_target.setdefault(a["id"], []).append(v)

    from untangle.answer.service import decision_card, ref_card

    revivals: list[Revival] = []
    readd = bool(_READD.search(prose)) if prose else False
    for t in targets:
        if t.label not in ("ConfigKey", "Dependency"):
            continue
        chain = sorted(by_target.get(t.id, []), key=lambda v: (v.valid_from or 0, v.created_at or 0))
        active = [v for v in chain if v.active]
        if active and (active[-1].object or "").strip().lower() == "removed" and (t.change == "edit" or (t.change == "mention" and readd)):
            earlier = next((v for v in reversed(chain) if not v.active and (v.object or "").strip().lower() != "removed"), None)
            if earlier is not None:
                reason, evidence = _replacement_reason(active[-1])
                revivals.append(Revival(target=t.key or t.name or t.id, proposed=t.proposed or "added again", replaced=decision_card(earlier),
                                        replaced_by=decision_card(active[-1]), reason=reason, evidence=ref_card(evidence) if evidence else None))
                continue
        if not t.proposed:
            continue
        if active and _norm(active[-1].object) == _norm(t.proposed):
            continue
        for v in reversed(chain):
            if v.active or _norm(v.object) != _norm(t.proposed):
                continue
            newer = next((n for n in chain if v.id in n.supersedes), None) or (active[-1] if active else None)
            if newer is None:
                continue
            reason, evidence = _replacement_reason(newer)
            revivals.append(Revival(target=t.key or t.name or t.id, proposed=t.proposed, replaced=decision_card(v),
                                    replaced_by=decision_card(newer), reason=reason, evidence=ref_card(evidence) if evidence else None))
            break

    guarded: list[GuardedDecision] = []
    for d in dossiers:
        head = d.top
        if not head.active or head.kind == "agent" and not head.rationale:
            continue
        guards, strength = _guards(head, len(d.versions) - 1)
        guarded.append(GuardedDecision(decision=decision_card(head), guards=guards, earlier_values=len(d.versions) - 1, strength=strength))
    guarded.sort(key=lambda g: (g.strength, g.earlier_values, g.decision.valid_from_iso or ""), reverse=True)
    other = len(other_roots) + max(0, len(guarded) - 15)
    guarded = guarded[:15]

    # -- reach ------------------------------------------------------------------------------------------------------
    target_paths = sorted({t.path for t in targets if t.label == "File" and t.path})
    reach = _reach(rec, repo, target_paths, imports_indexed)

    # -- advisories -------------------------------------------------------------------------------------------------
    adv = _advisories(targets, file_rows, http=http)

    # -- people -----------------------------------------------------------------------------------------------------
    people: list[PersonCard] = []
    owner_ids = [t.id for t in targets if t.label in ("File", "ConfigKey", "Dependency", "Module", "Symbol")][:20]
    if owner_ids:
        what = (targets[0].key or targets[0].path or targets[0].name or "this file") if len(targets) == 1 else "these files"
        for row in rec.run("person_to_ask", {"repo": repo, "ids": owner_ids, "now": now_ms, "limit": 3}):
            p = person_from_row(row)
            if p.counts and not _bot(p.login or p.name):
                people.append(PersonCard(id=p.id, name=p.name, login=p.login, why=p.why(what), score=round(p.score, 3)))

    review = _review(targets, revivals, guarded, reach, adv)
    return PreflightResponse(
        repo=repo, review=review, targets=targets, unresolved_paths=unresolved, revivals=revivals, decisions=guarded,
        other_decisions=other, reach=reach, advisories=adv, people=people,
        next_steps=_next_steps(revivals, guarded, reach, adv, people, unresolved),
        limits=_limits(imports_indexed, unresolved), cypher=rec.calls, ms=round((time.perf_counter() - started) * 1000, 1),
    )


_VERBS = frozenset("""add adds added readd re-add bring brings back bump bumps change changes changed delete deletes
    disable downgrade downgrades drop enable increase decrease lower raise remove removes rename replace replaces
    restore restores revert set sets switch update updates upgrade upgrades use move version value values instead
    generic core again new old latest pin pinned unpin""".split())
_READD = re.compile(r"\b(re-?add|add(?:ing)?\s+\S+\s+back|bring(?:ing)?\s+(?:\S+\s+)?back|restor(?:e|ing)|reintroduc(?:e|ing)|re-?enable|un-?remove)\b", re.IGNORECASE)


def _resolve_prose(rec: Recorder, repo: str, decision: Any, prose: str) -> list[Any]:
    """Entities a change description names. Unlike a question, a description lists several things in plain words
    ("downgrade mocha and drop chalk"), so each content word may name a dependency or configuration key exactly.
    Files, modules and symbols still need the router's own match, so ordinary words do not pull in code."""
    words = [w for w in re.findall(r"[A-Za-z@][\w@/.-]{2,}", prose) if w.lower() not in STOPWORDS and w.lower() not in _VERBS]
    words = [w.rstrip(".,;:") for w in words]
    base = decision
    extended = type(decision)(**{**decision.__dict__, "mentions": list(dict.fromkeys([*decision.mentions, *words]))[:40]})
    out: list[Any] = []
    deps: set[str] = set()
    for e in resolve_entities(rec, repo, extended, limit=10):
        if not e.matched:
            continue
        if e.label in ("File", "Module", "Symbol"):
            row = {"label": e.label, "name": e.name, "path": e.path, "key": e.key}
            if match_strength(row, base) < MATCH_THRESHOLD:
                continue
        if e.label == "Dependency":
            deps.add((e.name or "").lower())
        out.append(e)
    typed = {w.lower() for w in words}
    # `devDependencies.mocha` and `env.mocha` match the word `mocha` by their last segment; the dependency wins
    # unless the whole key was typed.
    return [e for e in out if not (e.label == "ConfigKey" and e.key and e.key.lower() not in typed and e.key.rsplit(".", 1)[-1].lower() in deps)]


def _bot(name: str | None) -> bool:
    return bool(name) and (name.endswith("[bot]") or name.lower() in {"dependabot", "renovate", "github-actions", "greenkeeper"})


_TAG = re.compile(r"<[^>]+>")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def plain(text: str | None, limit: int = 200) -> str:
    """Rationale as one readable line: no HTML tags, Markdown links reduced to their text, cut at a word."""
    value = _MD_LINK.sub(r"\1", _TAG.sub(" ", text or ""))
    value = re.sub(r"\s+", " ", value.replace("**", "").replace("`", "")).strip()
    if len(value) <= limit:
        return value
    cut = value[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def _real_reason(v: Version) -> str | None:
    """The recorded rationale when it says more than the decision's own text or its source's title."""
    reason = plain(v.rationale)
    if not reason or len(reason) < 8:
        return None
    same = {(v.text or "").strip().lower(), ((v.where or {}).get("title") or "").strip().lower(), (v.object or "").strip().lower()}
    return None if reason.lower().rstrip(".") in {x.rstrip(".") for x in same} else reason


def _replacement_reason(v: Version) -> tuple[str | None, dict[str, Any] | None]:
    incident = next(iter(v.incidents), None)
    if incident:
        return f"It changed after incident {_ref_name(incident)}.", incident
    if v.motivated_by:
        return f"It changed for {_ref_name(v.motivated_by[0])}.", v.motivated_by[0]
    reason = _real_reason(v)
    if reason:
        return reason.rstrip(".…") + ".", v.where
    where = v.where
    if where:
        return f"It changed in {_ref_name(where)}{' on ' + fmt_date(where.get('created_at')) if where.get('created_at') else ''}.", where
    return None, None


def _ref_name(ref: dict[str, Any]) -> str:
    label = label_of(ref.get("id"), ref.get("labels"))
    number = ref.get("number")
    title = ref.get("title")
    if label == "PullRequest" and number:
        return f"PR #{number}" + (f" '{title}'" if title else "")
    if label == "Issue" and number:
        return f"#{number}" + (f" '{title}'" if title else "")
    if label == "Commit":
        sha = (ref.get("sha") or "")[:7]
        return f"commit {sha}" + (f" '{title}'" if title else "") if sha else (title or "a commit")
    return title or ref.get("path") or ref.get("id") or "the linked source"


def _guards(v: Version, earlier: int) -> tuple[list[str], int]:
    guards: list[str] = []
    strength = 0
    for incident in v.incidents[:2]:
        guards.append(f"Introduced after incident {_ref_name(incident)}")
        strength += 3
    for issue in [m for m in v.motivated_by if not m.get("is_incident")][:2]:
        guards.append(f"Motivated by {_ref_name(issue)}")
        strength += 2
    reason = _real_reason(v)
    if reason:
        guards.append(f"Recorded reason: {reason}")
        strength += 1
    if v.signal == "revert_commit":
        guards.append("Came from a revert, so the previous form was backed out once")
        strength += 2
    for c in v.contradicted_by[:1]:
        guards.append(f"A handover call contradicts it: {plain(c.get('text') or c.get('object'), 160)}")
        strength += 2
    for c in v.confirmed_by[:1]:
        guards.append("A handover call confirms it" + (f": {plain(c['rationale'], 160)}" if c.get("rationale") else ""))
        strength += 1
    if earlier:
        guards.append(f"Replaced {earlier} earlier value{'s' if earlier != 1 else ''}")
        strength += 1 if earlier < 3 else 2
    if v.decided_in and label_of(v.decided_in.get("id"), v.decided_in.get("labels")) == "PullRequest":
        guards.append(f"Decided in {_ref_name(v.decided_in)}")
        strength += 1
    return guards, strength


def _reach(rec: Recorder, repo: str, paths: list[str], imports_indexed: bool) -> Reach:
    reach = Reach(imports_indexed=imports_indexed)
    if not paths:
        return reach
    via: dict[str, list[str]] = {p: [p] for p in paths}
    hop_of: dict[str, int] = dict.fromkeys(paths, 0)
    frontier = list(paths)
    if imports_indexed:
        for hop in range(1, MAX_HOPS + 1):
            if not frontier or len(hop_of) >= MAX_REACHED + len(paths):
                break
            rows = rec.run("preflight_importers", {"repo": repo, "paths": frontier, "seen": list(hop_of), "limit": MAX_REACHED})
            nxt: list[str] = []
            for row in rows:
                src = row["source"]
                if src in hop_of:
                    continue
                hop_of[src] = hop
                via[src] = [src, *via[row["target"]]]
                nxt.append(src)
                if len(hop_of) >= MAX_REACHED + len(paths):
                    reach.truncated = True
                    break
            frontier = nxt
        reach.reached = [Reached(path=p, hop=h, via=via[p]) for p, h in sorted(hop_of.items(), key=lambda x: (x[1], x[0])) if h > 0]
        features = rec.run("map_features", {"repo": repo, "feature_offset": 0, "feature_limit": 200})
        for row in features:
            f = row["feature"]
            hits = [e for e in f.get("entrypoints") or [] if e in hop_of]
            if hits:
                best = min(hits, key=lambda e: (hop_of[e], e))
                reach.areas.append(Area(name=f.get("name") or f.get("id"), source=f.get("source"), via=via[best]))
        reach.areas.sort(key=lambda a: (len(a.via), a.name))
    rows = rec.run("preflight_cochange", {"repo": repo, "paths": paths, "max_files": COCHANGE_MAX_FILES, "limit": 12})
    for row in rows:
        total = int(row.get("total") or 0)
        together = int(row.get("together") or 0)
        if together < 2 or not total:
            continue
        reach.cochanged.append(CoChange(path=row["path"], together=together, total=total, share=round(together / total, 2)))
    candidates = [*paths, *[r.path for r in reach.reached], *[c.path for c in reach.cochanged]]
    reach.tests = list(dict.fromkeys(p for p in candidates if is_test(p)))[:20]
    return reach


def _advisories(targets: list[Target], file_rows: list[dict[str, Any]], *, http: Any = None) -> Advisories:
    ecosystems = {d["id"]: d.get("ecosystem") for row in file_rows for d in row.get("deps") or [] if d}
    wanted: list[tuple[Target, str, osv.Checked | None, osv.Checked | None]] = []
    for t in targets:
        if t.label != "Dependency" or t.change not in ("edit", "mention") or not t.proposed:
            continue
        eco = ecosystems.get(t.id) or _ecosystem_from_id(t.id)
        if not osv.osv_ecosystem(eco):
            continue
        wanted.append((t, eco, osv.checkable(t.proposed), osv.checkable(t.current)))
    if not wanted:
        return Advisories()
    packages = []
    for t, eco, proposed, current in wanted:
        for c in (proposed, current):
            if c:
                packages.append((eco, t.name or "", c.version))
    found = osv.lookup(packages, client=http, enabled=settings().advisories)
    out = Advisories(checked=found.checked, note=found.note)
    for t, eco, proposed, current in wanted:
        new_ids = set(found.affecting.get((eco, t.name or "", proposed.version), [])) if proposed else set()
        old_ids = set(found.affecting.get((eco, t.name or "", current.version), [])) if current else set()
        for vid in sorted(new_ids - old_ids):
            adv = found.details.get(vid) or osv.Advisory(id=vid, url=f"https://osv.dev/vulnerability/{vid}")
            out.introduced.append(AdvisoryHit(package=t.name or "", ecosystem=eco, version=proposed.version, exact=proposed.exact,
                                              current=t.current, advisory=adv.as_dict()))
        for vid in sorted(old_ids - new_ids):
            adv = found.details.get(vid) or osv.Advisory(id=vid, url=f"https://osv.dev/vulnerability/{vid}")
            out.fixed.append(AdvisoryHit(package=t.name or "", ecosystem=eco, version=current.version if current else "",
                                         exact=bool(current and current.exact), current=t.current, advisory=adv.as_dict()))
    if any(not (p and p.exact) for _, _, p, _ in wanted) and out.checked:
        out.note = "Version ranges were checked at their lowest allowed version; a lockfile decides what is installed."
    return out


def _ecosystem_from_id(dep_id: str) -> str | None:
    # dep:<repo>:<ecosystem>:<name> (see untangle.ids.dependency_id)
    parts = dep_id.split(":")
    return parts[-2] if len(parts) >= 4 else None


def _review(targets: list[Target], revivals: list[Revival], guarded: list[GuardedDecision], reach: Reach, adv: Advisories) -> Review:
    reasons: list[Reason] = []

    def give(points: int, text: str) -> None:
        reasons.append(Reason(points=points, text=text))

    for r in revivals[:2]:
        if r.proposed == "added again":
            give(30, f"Adds {r.target} back after a recorded decision removed it")
        else:
            give(30, f"Brings back {r.target} = {r.proposed}, a value a later decision replaced")
    if adv.introduced:
        names = ", ".join(sorted({a.package + "@" + a.version for a in adv.introduced}))
        give(min(40, 25 + 5 * (len(adv.introduced) - 1)), f"The proposed version is affected by {len(adv.introduced)} public advisor{'ies' if len(adv.introduced) != 1 else 'y'} the current one is not ({names})")
    incident_guarded = [g for g in guarded if any(x.startswith("Introduced after incident") for x in g.guards)]
    if incident_guarded:
        give(min(30, 15 * len(incident_guarded)), f"{len(incident_guarded)} decision{'s' if len(incident_guarded) != 1 else ''} in scope came from an incident")
    linked = [g for g in guarded if g not in incident_guarded and any(x.startswith(("Motivated by", "Came from a revert")) for x in g.guards)]
    if linked:
        give(min(20, 8 * len(linked)), f"{len(linked)} decision{'s' if len(linked) != 1 else ''} in scope link to an issue or a revert")
    contradicted = [g for g in guarded if any(x.startswith("A handover call contradicts") for x in g.guards)]
    if contradicted:
        give(10, "A handover call disagrees with the recorded value")
    def described(t: Target) -> bool:
        return any(a.id == t.id or (t.label == "File" and a.path == t.path) for g in guarded for a in g.decision.about)

    removed = [t for t in targets if t.change in ("remove", "delete") and described(t)]
    if removed:
        give(10, f"Removes {', '.join((t.key or t.name or t.path or '') for t in removed[:3])}, which an active decision describes")
    active = len(guarded)
    if active and not incident_guarded and not linked:
        give(min(12, 3 * active), f"{active} active decision{'s' if active != 1 else ''} describe{'s' if active == 1 else ''} the targets")
    n = len(reach.reached)
    if n:
        give(5 if n <= 5 else 10 if n <= 20 else 15, f"{n} file{'s' if n != 1 else ''} import{'s' if n == 1 else ''} the changed files, directly or within {MAX_HOPS} hops")
    if len(reach.areas) >= 2:
        give(10, f"Reaches {len(reach.areas)} code areas through imports")
    strong = [c for c in reach.cochanged if c.share >= 0.4]
    if strong:
        give(5, f"{len(strong)} other file{'s' if len(strong) != 1 else ''} usually change{'s' if len(strong) == 1 else ''} in the same commits")
    score = min(100, sum(r.points for r in reasons))
    level: Level = "high" if score >= 55 else "medium" if score >= 25 else "low"
    reasons.sort(key=lambda r: r.points, reverse=True)
    return Review(level=level, score=score, reasons=reasons)


def _next_steps(revivals: list[Revival], guarded: list[GuardedDecision], reach: Reach, adv: Advisories, people: list[PersonCard], unresolved: list[str]) -> list[Step]:
    steps: list[Step] = []
    for r in revivals[:2]:
        where = _ref_label(r.evidence) if r.evidence else "the replacing decision"
        action = f"adding {r.target} back" if r.proposed == "added again" else f"setting {r.target} back to {r.proposed}"
        why = f" {r.reason}" if r.reason and not r.reason.startswith("It changed in") else ""
        steps.append(Step(text=f"Read {where} before {action}.{why}",
                          href=f"/decisions/{r.replaced_by.id}"))
    for a in adv.introduced[:2]:
        steps.append(Step(text=f"Pick a {a.package} version outside {a.advisory.get('id')}" + (f" ({a.advisory.get('summary')})" if a.advisory.get("summary") else "") + ".",
                          href=a.advisory.get("url")))
    linked = {r.replaced_by.id for r in revivals}
    evidenced = [g for g in guarded if g.decision.id not in linked and g.guards and g.guards[0].startswith(_EVIDENCE_GUARDS)]
    for g in evidenced[:3]:
        name = _ref_label(g.decision.decided_in) if g.decision.decided_in else (g.decision.text or g.decision.object)
        steps.append(Step(text=f"Read {name} first. {g.guards[0]}.", href=f"/decisions/{g.decision.id}"))
    if people:
        p = people[0]
        steps.append(Step(text=f"Ask {p.name or p.login} for review: {p.why}."))
    if reach.tests:
        steps.append(Step(text="Run the tests that reach this change: " + ", ".join(reach.tests[:5]) + (f", and {len(reach.tests) - 5} more." if len(reach.tests) > 5 else ".")))
    strong = [c.path for c in reach.cochanged if c.share >= 0.4][:4]
    if strong:
        steps.append(Step(text="Check whether these usually-paired files need the same change: " + ", ".join(strong) + "."))
    if unresolved:
        steps.append(Step(text=f"{len(unresolved)} named path{'s are' if len(unresolved) != 1 else ' is'} not in the indexed snapshot (new, renamed or outside the import). Check them by hand."))
    if not steps:
        steps.append(Step(text="Nothing in the recorded history argues against this change. Review it as usual; the graph cannot see undocumented reasons."))
    return steps


_EVIDENCE_GUARDS = ("Introduced after incident", "Motivated by", "Recorded reason", "Came from a revert", "A handover call")


def _ref_label(ref: Ref | None) -> str:
    if ref is None:
        return "the source"
    sha = ref.id.rsplit("@", 1)[-1] if ref.kind == "Commit" and "@" in ref.id else None
    return _ref_name({"id": ref.id, "labels": [ref.kind], "number": ref.number, "title": ref.title, "sha": sha})


def _limits(imports_indexed: bool, unresolved: list[str], *, nothing: bool = False) -> list[str]:
    out = [
        "History shows recorded reasons only. A low review level means nothing recorded argues against the change, not that it is safe.",
    ]
    if imports_indexed:
        out.append(f"Reach follows static imports at the indexed snapshot for up to {MAX_HOPS} hops. Dynamic imports, reflection, configuration effects and calls between services are not followed.")
    else:
        out.append("Source imports are not indexed for this repository yet, so reach is limited to files that changed in the same commits.")
    out.append("Configuration keys and dependencies are matched by name inside the changed lines of each file.")
    if nothing:
        out.append("No indexed file, configuration key or dependency matched the input.")
    return out


__all__ = ["PreflightRequest", "PreflightResponse", "assignment", "is_test", "parse_change", "preflight", "prose_value"]
