"""Deterministic Decision rows: one `change` per merged pull request, one `revert` per revert commit and the explicit
"supersedes #N" links between them. Also the `DecisionRow` shape every other extractor (`config_history`, `docs`,
`extract_llm`) emits, so the loader records all of them with `21_record_decision` and links them with
`23_link_decisions` / `22_link_decision`.

Decision rows are chronological facts: the loader sorts them by `valid_from` before recording, and the Cypher
statement applies key-based supersession, so emitters only need to be right about the key and the time."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from kyun import ids
from kyun.ingest.git_history import CommitRecord
from kyun.ingest.github_api import PullRecord

log = logging.getLogger("kyun.ingest.decisions")

MAX_ABOUT_FILES = 10
MAX_RATIONALE_CHARS = 2000
MAX_TEXT_CHARS = 500

_CLOSES = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*(?:https?://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/)?#?(\d+)", re.IGNORECASE)
_MENTION = re.compile(r"(?<![\w/&])#(\d{1,6})\b")
_URL_MENTION = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/(\d+)")
_SUPERSEDES = re.compile(r"\b(?:supersedes|replaces|reverts|obsoletes)\s*:?\s*(?:PR\s*)?(?:https?://github\.com/[\w.-]+/[\w.-]+/pull/)?#?(\d+)", re.IGNORECASE)
_WS = re.compile(r"\s+")


@dataclass(slots=True)
class DecisionRow:
    """One row for `21_record_decision` plus its outgoing links (`rel`, `target_id`, props)."""

    id: str
    repo: str
    kind: str
    key: str
    subject: str
    predicate: str
    object: str
    text: str
    rationale: str | None
    valid_from: int
    confidence: float
    signal: str
    created_at: int | None = None
    order: int = 0  # tie-breaker for rows with the same valid_from (git-log position)
    links: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def link(self, rel: str, target_id: str | None, **props: Any) -> None:
        if target_id and (rel, target_id) not in {(r, t) for r, t, _ in self.links}:
            self.links.append((rel, target_id, props))

    def as_row(self) -> dict[str, Any]:
        return {
            "id": self.id, "repo": self.repo, "kind": self.kind, "key": self.key.lower(), "subject": self.subject,
            "predicate": self.predicate, "object": self.object, "text": self.text[:MAX_TEXT_CHARS],
            "rationale": (self.rationale or None) and self.rationale[:MAX_RATIONALE_CHARS], "valid_from": int(self.valid_from),
            "confidence": float(self.confidence), "signal": self.signal, "created_at": self.created_at,
        }


def make_decision(repo: str, kind: str, key: str, anchor: str, **fields: Any) -> DecisionRow:
    """Build a row with its deterministic id (`anchor` makes the instance unique: a sha, a PR number, a path)."""
    key = key.lower()
    return DecisionRow(id=ids.decision_id(repo, kind, key, anchor), repo=repo, kind=kind, key=key, **fields)


# -- text helpers shared with github_api / docs ---------------------------------------------------
def first_paragraph(text: str | None, limit: int = MAX_RATIONALE_CHARS) -> str | None:
    """The first non-heading, non-boilerplate paragraph of a PR/issue body (markdown comments stripped)."""
    if not text:
        return None
    cleaned = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    for block in re.split(r"\n\s*\n", cleaned.strip()):
        block = block.strip()
        if not block or block.startswith(("#", "<", "|", "```", "- [ ]", "- [x]", "![")):
            continue
        return _WS.sub(" ", block)[:limit]
    return None


def closes_numbers(text: str | None) -> list[int]:
    return _dedupe(int(n) for n in _CLOSES.findall(text or ""))


def mentioned_numbers(text: str | None) -> list[int]:
    found = [int(n) for n in _MENTION.findall(text or "")] + [int(n) for n in _URL_MENTION.findall(text or "")]
    return _dedupe(found)


def supersedes_numbers(text: str | None) -> list[int]:
    return _dedupe(int(n) for n in _SUPERSEDES.findall(text or ""))


def _dedupe(numbers: Iterable[int]) -> list[int]:
    return list(dict.fromkeys(n for n in numbers if 0 < n < 10_000_000))


# -- change decisions per merged PR ---------------------------------------------------------------
def pr_change_decisions(
    repo: str,
    prs: Iterable[PullRecord],
    commits_by_sha: dict[str, CommitRecord],
    pr_commit_shas: dict[int, list[str]],
    issue_numbers: set[int],
    comment_ids_by_pr: dict[int, list[str]],
    person_id_for_login: dict[str, str],
) -> list[DecisionRow]:
    """One `change` decision per merged PR with ABOUT the most-changed files, DECIDED_IN the PR, EVIDENCED_BY its
    reviews/comments, STATED_BY the author, MOTIVATED_BY the issues it closes and IMPLEMENTED_BY its commits."""
    rows: list[DecisionRow] = []
    for pr in prs:
        if not pr.merged or not pr.merged_at:
            continue
        key = f"pr#{pr.number}|changed"
        row = make_decision(
            repo, "change", key, str(pr.number),
            subject=f"pr#{pr.number}", predicate="changed", object=pr.title.strip()[:MAX_TEXT_CHARS] or f"PR #{pr.number}",
            text=f"PR #{pr.number}: {pr.title.strip()}"[:MAX_TEXT_CHARS], rationale=first_paragraph(pr.body),
            valid_from=pr.merged_at, confidence=0.9, signal="pr_merge",
        )
        row.link("DECIDED_IN", ids.pr_id(repo, pr.number))
        if pr.author_login:
            row.link("STATED_BY", person_id_for_login.get(pr.author_login.lower(), ids.person_id(login=pr.author_login)))
        for n in closes_numbers(pr.body):
            if n in issue_numbers:
                row.link("MOTIVATED_BY", ids.issue_id(repo, n))
        churn: dict[str, int] = {}
        for sha in pr_commit_shas.get(pr.number, []):
            commit = commits_by_sha.get(sha)
            if commit is None:
                continue
            row.link("IMPLEMENTED_BY", ids.commit_id(repo, sha))
            for n in closes_numbers(commit.message):
                if n in issue_numbers:
                    row.link("MOTIVATED_BY", ids.issue_id(repo, n))
            for fc in commit.files:
                churn[fc.path] = churn.get(fc.path, 0) + (fc.additions or 0) + (fc.deletions or 0) + 1
        for path, _ in sorted(churn.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_ABOUT_FILES]:
            row.link("ABOUT", ids.file_id(repo, path))
        for cid in comment_ids_by_pr.get(pr.number, [])[:50]:
            row.link("EVIDENCED_BY", cid)
        rows.append(row)
    return rows


# -- reverts ------------------------------------------------------------------------------------------
def revert_decisions(
    repo: str,
    commits: Iterable[CommitRecord],
    commits_by_sha: dict[str, CommitRecord],
    decisions_by_commit_id: dict[str, list[str]],
    person_id_for_email: dict[str, str],
) -> list[DecisionRow]:
    """A `revert` decision per revert commit whose target is in the history. It SUPERSEDES (signal `revert_commit`)
    every decision the reverted commit implemented (`decisions_by_commit_id` maps a Commit node id to decision ids):
    its config/dependency decisions and the PR change decision."""
    rows: list[DecisionRow] = []
    by_prefix = {sha: sha for sha in commits_by_sha}
    for commit in commits:
        if not commit.is_revert or not commit.reverts_sha:
            continue
        target_sha = _resolve_sha(commit.reverts_sha, by_prefix)
        if target_sha is None:
            continue
        target = commits_by_sha[target_sha]
        key = f"revert|{ids.short_sha(target_sha)}|reverted"
        row = make_decision(
            repo, "revert", key, commit.sha,
            subject=f"commit {ids.short_sha(target_sha)}", predicate="reverted", object=ids.short_sha(commit.sha),
            text=f"Commit {ids.short_sha(target_sha)} ({target.title}) was reverted by {ids.short_sha(commit.sha)}"[:MAX_TEXT_CHARS],
            rationale=_revert_reason(commit.message), valid_from=commit.authored_at, confidence=0.95, signal="revert_commit",
        )
        row.link("DECIDED_IN", ids.commit_id(repo, commit.sha))
        row.link("IMPLEMENTED_BY", ids.commit_id(repo, commit.sha))
        row.link("EVIDENCED_BY", ids.commit_id(repo, target_sha))
        row.link("STATED_BY", person_id_for_email.get(commit.author_email, ids.person_id(email=commit.author_email)))
        for fc in target.files[:MAX_ABOUT_FILES]:
            row.link("ABOUT", ids.file_id(repo, fc.path))
        for dec_id in decisions_by_commit_id.get(ids.commit_id(repo, target_sha), []):
            row.link("SUPERSEDES", dec_id, signal="revert_commit", at=commit.authored_at)
        rows.append(row)
    return rows


def _resolve_sha(prefix: str, shas: dict[str, str]) -> str | None:
    if prefix in shas:
        return prefix
    matches = [s for s in shas if s.startswith(prefix)]
    return matches[0] if len(matches) == 1 else None


def _revert_reason(message: str) -> str | None:
    lines = [ln.strip() for ln in message.splitlines()[1:] if ln.strip() and not ln.strip().startswith("This reverts commit")]
    return _WS.sub(" ", " ".join(lines))[:MAX_RATIONALE_CHARS] or None


# -- explicit supersession between PR change decisions ---------------------------------------------
def explicit_supersessions(repo: str, prs: Iterable[PullRecord], change_rows: dict[int, DecisionRow]) -> int:
    """"supersedes #N" / "replaces #N" / "reverts #N" in a merged PR body links its change decision over #N's."""
    added = 0
    for pr in prs:
        row = change_rows.get(pr.number)
        if row is None:
            continue
        for n in supersedes_numbers(pr.body):
            older = change_rows.get(n)
            if older is not None and n != pr.number:
                row.link("SUPERSEDES", older.id, signal="supersedes_text", at=row.valid_from)
                added += 1
    return added


__all__ = [
    "DecisionRow", "closes_numbers", "explicit_supersessions", "first_paragraph", "make_decision", "mentioned_numbers",
    "pr_change_decisions", "revert_decisions", "supersedes_numbers",
]
