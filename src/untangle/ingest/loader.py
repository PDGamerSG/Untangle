"""Row shaping and batched `UNWIND $rows` MERGE writes through the numbered Cypher statements (`cypher/10_*` …
`17_*`, `21`–`23`). Everything here is idempotent: ids come from `untangle.ids`, nodes are MERGEd on `id` and
properties SET, so re-running an ingestion rewrites the same graph.

`People` resolves identities: one Person per GitHub login when it is known (a PR's commit list reveals
`email -> login`), else one per email; every email and login also gets an Identity node pointing at the Person."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from untangle import ids
from untangle.graph.db import Graph
from untangle.graph.queries import load_cypher
from untangle.ingest.config_history import KeyState
from untangle.ingest.decisions import DecisionRow, closes_numbers, mentioned_numbers
from untangle.ingest.docs import DocumentRecord
from untangle.ingest.git_history import CommitRecord
from untangle.ingest.github_api import GitHubData, PullRecord
from untangle.ingest.symbols import ConfigKeyRecord, DependencyRecord, SymbolRecord, is_config_path, is_doc_path

log = logging.getLogger("untangle.ingest.loader")

BATCH = 500
CHUNK_BATCH = 200
MAX_REFERENCES_PER_SOURCE = 20
MAX_TEXT = 20_000


def _batches(rows: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _clip(text: str | None, limit: int = MAX_TEXT) -> str | None:
    return None if text is None else text[:limit]


# -- people ---------------------------------------------------------------------------------------------
class People:
    """Collects Person and Identity rows while the other row builders run."""

    def __init__(self, email_to_login: dict[str, str] | None = None, login_names: dict[str, str] | None = None):
        self.email_to_login = {k.lower(): v for k, v in (email_to_login or {}).items() if k and v}
        self.login_names = dict(login_names or {})
        self.persons: dict[str, dict[str, Any]] = {}
        self.identities: dict[str, dict[str, Any]] = {}

    def _ensure(self, pid: str, *, name: str | None = None, login: str | None = None, email: str | None = None) -> str:
        p = self.persons.get(pid)
        if p is None:
            p = {"id": pid, "name": name or login or email or "unknown", "login": login, "email": email, "kind": "contributor"}
            self.persons[pid] = p
        else:
            if name and (not p["name"] or p["name"] in (p["login"], p["email"])):
                p["name"] = name
            p["login"] = p["login"] or login
            p["email"] = p["email"] or email
        local = (p["email"] or "").split("@")[0]
        p["tokens"] = ids.tokens(" ".join(x for x in (p["name"], p["login"], local) if x))
        return pid

    def _identity(self, kind: str, value: str, pid: str) -> None:
        iid = ids.identity_id(kind, value)
        self.identities[iid] = {"id": iid, "kind": kind, "value": value.lower(), "person_id": pid}

    def for_email(self, name: str | None, email: str | None) -> str:
        """Commit author/committer: the login's Person when the email is known to belong to one."""
        email = (email or "").strip().lower() or None
        login = self.email_to_login.get(email) if email else None
        if login:
            pid = self._ensure(ids.person_id(login=login), name=name, login=login, email=email)
            self._identity("login", login, pid)
        elif email:
            pid = self._ensure(ids.person_id(email=email), name=name, email=email)
        else:
            pid = self._ensure(ids.person_id(name=name), name=name)
        if email:
            self._identity("email", email, pid)
        return pid

    def for_login(self, login: str | None) -> str | None:
        if not login:
            return None
        pid = self._ensure(ids.person_id(login=login), name=self.login_names.get(login), login=login)
        self._identity("login", login, pid)
        return pid

    @property
    def person_id_for_login(self) -> dict[str, str]:
        return {p["login"].lower(): pid for pid, p in self.persons.items() if p.get("login")}

    @property
    def person_id_for_email(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for ident in self.identities.values():
            if ident["kind"] == "email":
                out[ident["value"]] = ident["person_id"]
        return out

    def rows(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return list(self.persons.values()), list(self.identities.values())


# -- git rows -------------------------------------------------------------------------------------------
def commit_rows(repo: str, commits: Iterable[CommitRecord], people: People) -> list[dict[str, Any]]:
    rows = []
    for c in commits:
        rows.append({
            "id": ids.commit_id(repo, c.sha), "repo": repo, "sha": c.sha, "title": c.title, "message": _clip(c.message),
            "authored_at": c.authored_at, "committed_at": c.committed_at, "is_merge": c.is_merge, "is_revert": c.is_revert,
            "reverts_sha": c.reverts_sha, "url": f"https://github.com/{repo}/commit/{c.sha}", "additions": c.additions,
            "deletions": c.deletions, "files_changed": c.files_changed,
            "author_id": people.for_email(c.author_name, c.author_email),
            "committer_id": people.for_email(c.committer_name, c.committer_email),
        })
    return rows


@dataclass(slots=True)
class FileRows:
    files: list[dict[str, Any]] = field(default_factory=list)
    modules_by_depth: list[list[dict[str, Any]]] = field(default_factory=list)
    touched: list[dict[str, Any]] = field(default_factory=list)
    renames: list[dict[str, Any]] = field(default_factory=list)
    first_seen_at: dict[str, int] = field(default_factory=dict)
    first_author: dict[str, str] = field(default_factory=dict)  # path -> person id of the adding commit's author


def file_rows(repo: str, commits: Iterable[CommitRecord], head_files: dict[str, int], people: People) -> FileRows:
    """File, Module, TOUCHED and RENAMED_FROM rows from the history plus the HEAD listing (`alive`)."""
    out = FileRows()
    stats: dict[str, dict[str, Any]] = {}
    for c in sorted(commits, key=lambda c: (c.authored_at, c.sha)):
        cid = ids.commit_id(repo, c.sha)
        for fc in c.files:
            st = stats.setdefault(fc.path, {"first": c.authored_at, "last": c.authored_at, "n": 0})
            st["first"], st["last"], st["n"] = min(st["first"], c.authored_at), max(st["last"], c.authored_at), st["n"] + 1
            if fc.change == "A" and fc.path not in out.first_author:
                out.first_author[fc.path] = people.for_email(c.author_name, c.author_email)
            out.touched.append({"commit_id": cid, "file_id": ids.file_id(repo, fc.path), "change": fc.change,
                                "additions": fc.additions, "deletions": fc.deletions})
            if fc.change == "R" and fc.old_path:
                stats.setdefault(fc.old_path, {"first": c.authored_at, "last": c.authored_at, "n": 0})
                out.renames.append({"new_id": ids.file_id(repo, fc.path), "old_id": ids.file_id(repo, fc.old_path), "at": c.authored_at, "sha": c.sha})
    for path in head_files:
        stats.setdefault(path, {"first": None, "last": None, "n": 0})
    modules: dict[str, dict[str, Any]] = {}

    def module_for(directory: str) -> str:
        directory = directory or "."
        mid = ids.module_id(repo, directory)
        if mid not in modules:
            parent = None if directory == "." else str(PurePosixPath(directory).parent)
            parent = "." if parent in ("", ".") else parent
            modules[mid] = {"id": mid, "repo": repo, "path": directory, "name": PurePosixPath(directory).name or directory,
                            "tokens": ids.tokens(directory), "parent_id": None if directory == "." else module_for(parent),
                            "depth": 0 if directory == "." else directory.count("/") + 1}
        return mid

    for path, st in stats.items():
        p = PurePosixPath(path)
        parent = str(p.parent)
        out.files.append({
            "id": ids.file_id(repo, path), "repo": repo, "path": path, "name": p.name, "ext": p.suffix.lower().lstrip("."),
            "tokens": ids.tokens(path), "is_config": is_config_path(path), "is_doc": is_doc_path(path), "alive": path in head_files,
            "first_seen_at": st["first"], "last_touched_at": st["last"], "touch_count": st["n"],
            "module_id": module_for("." if parent in ("", ".") else parent),
        })
        if st["first"] is not None:
            out.first_seen_at[path] = st["first"]
    max_depth = max((m["depth"] for m in modules.values()), default=0)
    out.modules_by_depth = [[m for m in modules.values() if m["depth"] == d] for d in range(max_depth + 1)]
    return out


def symbol_rows(repo: str, symbols: Iterable[SymbolRecord]) -> list[dict[str, Any]]:
    return [{"id": ids.symbol_id(repo, s.path, s.name), "repo": repo, "name": s.name, "kind": s.kind, "path": s.path, "line": s.line,
             "tokens": ids.tokens(s.name), "file_id": ids.file_id(repo, s.path)} for s in symbols]


def config_key_rows(repo: str, head_keys: Iterable[ConfigKeyRecord], states: dict[tuple[str, str], KeyState]) -> list[dict[str, Any]]:
    """HEAD values win for `current_value`; the history supplies `current_since` and keys that were removed."""
    rows: dict[str, dict[str, Any]] = {}
    for k in head_keys:
        state = states.get((k.path, k.key))
        rows[ids.config_key_id(repo, k.path, k.key)] = {
            "id": ids.config_key_id(repo, k.path, k.key), "repo": repo, "key": k.key, "path": k.path, "tokens": ids.tokens(f"{k.key} {k.path}"),
            "current_value": k.value, "current_since": state.since if state else None, "file_id": ids.file_id(repo, k.path),
        }
    for (path, key), state in states.items():
        cid = ids.config_key_id(repo, path, key)
        if cid in rows:
            rows[cid]["current_since"] = state.since
            continue
        rows[cid] = {"id": cid, "repo": repo, "key": key, "path": path, "tokens": ids.tokens(f"{key} {path}"),
                     "current_value": state.value, "current_since": state.since, "file_id": ids.file_id(repo, path)}
    return list(rows.values())


def dependency_rows(repo: str, head_deps: Iterable[DependencyRecord], states: dict[tuple[str, str], KeyState]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for d in head_deps:
        did = ids.dependency_id(repo, d.ecosystem, d.name)
        rows[did] = {"id": did, "repo": repo, "name": d.name, "ecosystem": d.ecosystem, "tokens": ids.tokens(d.name),
                     "current_version": d.version or "*", "file_id": ids.file_id(repo, d.path)}
    for (path, name), state in states.items():
        did = ids.dependency_id(repo, state.ecosystem or "other", name)
        if did not in rows:
            rows[did] = {"id": did, "repo": repo, "name": name, "ecosystem": state.ecosystem or "other", "tokens": ids.tokens(name),
                         "current_version": state.value, "file_id": ids.file_id(repo, path)}
    return list(rows.values())


# -- github rows ----------------------------------------------------------------------------------------
@dataclass(slots=True)
class GitHubRows:
    prs: list[dict[str, Any]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    comments: list[dict[str, Any]] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)
    pr_commits: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    pr_commit_shas: dict[int, list[str]] = field(default_factory=dict)
    pr_by_sha: dict[str, PullRecord] = field(default_factory=dict)
    comment_ids_by_pr: dict[int, list[str]] = field(default_factory=dict)
    issue_numbers: set[int] = field(default_factory=set)


def _target_id(repo: str, n: int, issue_numbers: set[int], pr_numbers: set[int]) -> str | None:
    if n in issue_numbers:
        return ids.issue_id(repo, n)
    if n in pr_numbers:
        return ids.pr_id(repo, n)
    return None


def github_rows(repo: str, gh: GitHubData, commits_by_sha: dict[str, CommitRecord], people: People) -> GitHubRows:
    out = GitHubRows()
    out.issue_numbers = {i.number for i in gh.issues}
    pr_numbers = set(gh.pr_numbers) | {pr.number for pr in gh.prs}
    for pr in sorted(gh.prs, key=lambda p: (not p.merged, p.number)):
        pid = ids.pr_id(repo, pr.number)
        shas = [c.sha for c in pr.commits] + ([pr.merge_commit_sha] if pr.merge_commit_sha else [])
        linked = [s for s in dict.fromkeys(shas) if s in commits_by_sha]
        out.pr_commit_shas[pr.number] = linked
        for sha in linked:
            out.pr_by_sha.setdefault(sha, pr)
            out.pr_commits.append({"commit_id": ids.commit_id(repo, sha), "pr_id": pid})
        changed = {fc.path for s in linked for fc in commits_by_sha[s].files}
        out.prs.append({
            "id": pid, "repo": repo, "number": pr.number, "title": pr.title, "body": _clip(pr.body), "state": pr.state, "merged": pr.merged,
            "created_at": pr.created_at, "merged_at": pr.merged_at, "closed_at": pr.closed_at, "url": pr.url, "author_login": pr.author_login,
            "labels": pr.labels, "additions": sum(commits_by_sha[s].additions for s in linked), "deletions": sum(commits_by_sha[s].deletions for s in linked),
            "changed_files": len(changed), "author_id": people.for_login(pr.author_login),
        })
        closes = [n for n in closes_numbers(pr.body) if n in out.issue_numbers]
        for n in closes:
            out.references.append({"from_id": pid, "rel": "CLOSES", "to_id": ids.issue_id(repo, n)})
        for n in [m for m in mentioned_numbers(f"{pr.title}\n{pr.body}") if m not in closes and m != pr.number][:MAX_REFERENCES_PER_SOURCE]:
            if target := _target_id(repo, n, out.issue_numbers, pr_numbers):
                out.references.append({"from_id": pid, "rel": "REFERENCES", "to_id": target})
        cids: list[str] = []
        for r in sorted(pr.reviews, key=lambda r: r.submitted_at or 0):
            person = people.for_login(r.author_login)
            if person:
                out.reviews.append({"person_id": person, "pr_id": pid, "state": r.state, "at": r.submitted_at or 0})
            if r.body.strip():
                cid = ids.comment_id(repo, "pr_review", r.id)
                cids.append(cid)
                out.comments.append({"id": cid, "repo": repo, "kind": "pr_review", "body": _clip(r.body), "created_at": r.submitted_at, "url": r.url,
                                     "author_login": r.author_login, "path": None, "line": None, "review_state": r.state, "on_id": pid,
                                     "author_id": person, "file_id": None})
        for c in pr.review_comments + pr.comments:
            cid = ids.comment_id(repo, c.kind, c.id)
            cids.append(cid)
            out.comments.append({"id": cid, "repo": repo, "kind": c.kind, "body": _clip(c.body), "created_at": c.created_at, "url": c.url,
                                 "author_login": c.author_login, "path": c.path, "line": c.line, "review_state": None, "on_id": pid,
                                 "author_id": people.for_login(c.author_login), "file_id": ids.file_id(repo, c.path) if c.path else None})
        out.comment_ids_by_pr[pr.number] = cids
    for issue in gh.issues:
        iid = ids.issue_id(repo, issue.number)
        out.issues.append({
            "id": iid, "repo": repo, "number": issue.number, "title": issue.title, "body": _clip(issue.body), "state": issue.state, "labels": issue.labels,
            "created_at": issue.created_at, "closed_at": issue.closed_at, "url": issue.url, "author_login": issue.author_login,
            "is_incident": issue.is_incident, "author_id": people.for_login(issue.author_login),
        })
        for n in [m for m in mentioned_numbers(f"{issue.title}\n{issue.body}") if m != issue.number][:MAX_REFERENCES_PER_SOURCE]:
            if target := _target_id(repo, n, out.issue_numbers, pr_numbers):
                out.references.append({"from_id": iid, "rel": "REFERENCES", "to_id": target})
        for c in issue.comments:
            out.comments.append({"id": ids.comment_id(repo, c.kind, c.id), "repo": repo, "kind": c.kind, "body": _clip(c.body), "created_at": c.created_at,
                                 "url": c.url, "author_login": c.author_login, "path": None, "line": None, "review_state": None, "on_id": iid,
                                 "author_id": people.for_login(c.author_login), "file_id": None})
    for sha, commit in commits_by_sha.items():
        for n in mentioned_numbers(commit.message)[:MAX_REFERENCES_PER_SOURCE]:
            if target := _target_id(repo, n, out.issue_numbers, pr_numbers):
                out.references.append({"from_id": ids.commit_id(repo, sha), "rel": "REFERENCES", "to_id": target})
    return out


def document_rows(repo: str, docs: Iterable[DocumentRecord]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, links = [], []
    for d in docs:
        rows.append({"id": ids.document_id(repo, d.path), "repo": repo, "path": d.path, "title": d.title, "kind": d.kind, "status": d.status,
                     "adr_number": d.adr_number, "date": d.date, "text": _clip(d.text, 40_000), "superseded_by_path": d.superseded_by_path,
                     "file_id": ids.file_id(repo, d.path)})
        if d.superseded_by_path:
            links.append({"old_id": ids.document_id(repo, d.path), "new_id": ids.document_id(repo, d.superseded_by_path)})
    return rows, links


def revert_rows(repo: str, commits: Iterable[CommitRecord], commits_by_sha: dict[str, CommitRecord]) -> list[dict[str, Any]]:
    rows = []
    for c in commits:
        if not c.reverts_sha:
            continue
        matches = [s for s in commits_by_sha if s.startswith(c.reverts_sha)]
        if len(matches) == 1:
            rows.append({"revert_id": ids.commit_id(repo, c.sha), "reverted_id": ids.commit_id(repo, matches[0])})
    return rows


# -- writer ------------------------------------------------------------------------------------------------
class Loader:
    """Writes rows through the named statements and keeps per-statement counts."""

    def __init__(self, graph: Graph, repo: str, *, batch_size: int = BATCH):
        self.graph, self.repo, self.batch_size = graph, repo, batch_size
        self.counts: dict[str, int] = {}

    def write(self, name: str, rows: list[dict[str, Any]], *, batch_size: int | None = None) -> int:
        if not rows:
            return 0
        n = self.graph.write_batches(load_cypher(name), rows, batch_size=batch_size or self.batch_size)
        self.counts[name] = self.counts.get(name, 0) + n
        log.debug("%s: %d rows", name, n)
        return n

    def people(self, people: People) -> tuple[int, int]:
        persons, identities = people.rows()
        return self.write("10_upsert_people", persons), self.write("10_upsert_identities", identities)

    def files(self, rows: FileRows) -> dict[str, int]:
        for level in rows.modules_by_depth:
            self.write("12_upsert_modules", level)
        return {
            "files": self.write("12_upsert_files", rows.files), "touched": self.write("12_upsert_touched", rows.touched),
            "renames": self.write("12_upsert_renames", rows.renames),
        }

    def github(self, rows: GitHubRows) -> dict[str, int]:
        return {
            "prs": self.write("14_upsert_prs", rows.prs), "issues": self.write("14_upsert_issues", rows.issues),
            "comments": self.write("14_upsert_comments", rows.comments), "reviews": self.write("14_upsert_reviews", rows.reviews),
            "pr_commits": self.write("14_link_pr_commits", rows.pr_commits), "references": self.write("14_link_references", rows.references),
        }

    def decisions(self, rows: list[DecisionRow]) -> dict[str, int]:
        """Record chronologically with `21_record_decision`, then link (bulk through `23`, explicit SUPERSEDES
        through the foundation's `22`). Returns recorded / superseded / linked counts."""
        ordered = sorted(rows, key=lambda r: (r.valid_from, r.order, r.id))
        now = int(time.time() * 1000)
        record, superseded = load_cypher("21_record_decision"), 0
        # Rounds: the k-th row of every key goes in round k, so one UNWIND batch never holds two rows of the same
        # key (Cypher runs each clause over all rows before the next, and two same-key rows in a batch would see
        # each other's half-written state and produce `late_import` edges in the wrong direction).
        rounds: list[list[DecisionRow]] = []
        seen_per_key: dict[str, int] = {}
        for r in ordered:
            k = seen_per_key.get(r.key, 0)
            seen_per_key[r.key] = k + 1
            while len(rounds) <= k:
                rounds.append([])
            rounds[k].append(r)
        for round_rows in rounds:
            for batch in _batches([r.as_row() for r in round_rows], self.batch_size):
                res = self.graph.query(record, {"rows": batch, "now": now})
                superseded += sum(len(rec["superseded"] or []) for rec in res.records)
        seen: set[tuple[str, str, str]] = set()
        links: list[dict[str, Any]] = []
        for r in ordered:
            for rel, target, props in r.links:
                if (r.id, rel, target) not in seen:
                    seen.add((r.id, rel, target))
                    links.append({"decision_id": r.id, "rel": rel, "target_id": target, "props": props or {}})
        explicit = [link for link in links if link["rel"] == "SUPERSEDES"]
        bulk = [link for link in links if link["rel"] != "SUPERSEDES"]
        linked = 0
        for batch in _batches(bulk, self.batch_size):
            linked += int(self.graph.query(load_cypher("23_link_decisions"), {"rows": batch, "now": now}).scalar(0) or 0)
        for batch in _batches(explicit, 100):
            linked += int(self.graph.query(load_cypher("22_link_decision"), {"rows": batch, "now": now}).scalar(0) or 0)
        self.counts["21_record_decision"] = self.counts.get("21_record_decision", 0) + len(ordered)
        self.counts["links"] = self.counts.get("links", 0) + linked
        return {"recorded": len(ordered), "superseded": superseded, "links_requested": len(links), "linked": linked}

    def chunks(self, rows: list[dict[str, Any]]) -> int:
        return self.write("16_upsert_chunks", rows, batch_size=CHUNK_BATCH)

    def repo_node(self, row: dict[str, Any]) -> None:
        self.graph.query(load_cypher("10_upsert_repo"), {"row": row})


__all__ = [
    "FileRows", "GitHubRows", "Loader", "People", "commit_rows", "config_key_rows", "dependency_rows", "document_rows",
    "file_rows", "github_rows", "revert_rows", "symbol_rows",
]
