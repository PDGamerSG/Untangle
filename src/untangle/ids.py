"""Stable, human-readable node ids. Every id is deterministic from its source so re-ingesting is idempotent
(MERGE on id) and ids can be quoted as citations: `pr:knadh/listmonk#812`, `commit:knadh/listmonk@3fa2c1d`.

Also the text helpers shared by ingestion and the answer router: `tokens()` splits identifiers so that
`retry_limit`, `RetryLimit` and "retry limit" all land on the same full-text terms."""

from __future__ import annotations

import hashlib
import re

_SPLIT = re.compile(r"[^0-9A-Za-zऀ-ॿ]+")  # keep Devanagari letters whole
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def tokens(text: str) -> str:
    """Lower-cased, space-separated tokens of an identifier or path: `cmd/retry_limit.go` -> `cmd retry limit go`."""
    parts: list[str] = []
    for raw in _SPLIT.split(text or ""):
        if not raw:
            continue
        for piece in _CAMEL.split(raw):
            if piece:
                parts.append(piece.lower())
    return " ".join(dict.fromkeys(parts))


def short_sha(sha: str) -> str:
    return (sha or "")[:12]


def digest(*parts: str, n: int = 12) -> str:
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:n]


def repo_id(full_name: str) -> str:
    return f"repo:{full_name}"


def commit_id(repo: str, sha: str) -> str:
    return f"commit:{repo}@{short_sha(sha)}"


def file_id(repo: str, path: str) -> str:
    return f"file:{repo}:{path}"


def module_id(repo: str, path: str) -> str:
    return f"module:{repo}:{path or '.'}"


def symbol_id(repo: str, path: str, name: str) -> str:
    return f"sym:{repo}:{path}::{name}"


def config_key_id(repo: str, path: str, key: str) -> str:
    return f"cfg:{repo}:{path}::{key}"


def dependency_id(repo: str, ecosystem: str, name: str) -> str:
    return f"dep:{repo}:{ecosystem}:{name.lower()}"


def pr_id(repo: str, number: int) -> str:
    return f"pr:{repo}#{int(number)}"


def issue_id(repo: str, number: int) -> str:
    return f"issue:{repo}#{int(number)}"


def comment_id(repo: str, kind: str, raw_id: int | str) -> str:
    return f"comment:{repo}:{kind}:{raw_id}"


def document_id(repo: str, path: str) -> str:
    return f"doc:{repo}:{path}"


def chunk_id(source_id: str, seq: int) -> str:
    return f"chunk:{source_id}#{int(seq)}"


def person_id(login: str | None = None, email: str | None = None, name: str | None = None) -> str:
    if login:
        return f"person:gh:{login.lower()}"
    if email:
        return f"person:email:{email.lower()}"
    return f"person:name:{digest(name or 'unknown')}"


def identity_id(kind: str, value: str) -> str:
    return f"identity:{kind}:{value.lower()}"


def decision_id(repo: str, kind: str, key: str, anchor: str) -> str:
    """`anchor` is what makes this decision instance unique (a commit sha, PR number, ADR path or utterance id)."""
    return f"dec:{repo}:{kind}:{digest(key, anchor)}"


def meeting_id(repo: str, slug: str) -> str:
    return f"mtg:{repo}:{slug}"


def utterance_id(meeting: str, seq: int) -> str:
    return f"utt:{meeting}#{int(seq):04d}"
