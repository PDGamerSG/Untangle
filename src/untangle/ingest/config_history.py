"""Configuration values and dependency versions over time.

For every configuration file and dependency manifest, the commits that touched it are walked oldest to newest,
each version is read with one `git cat-file --batch` call, flattened, and the scalar values diffed against the
previous version. Every change is a `config_value` (or `dependency`) Decision whose rationale is the commit
title and, when the commit belongs to a pull request, the PR title. `21_record_decision` applies the key-based
supersession, so a key's history becomes a `SUPERSEDES` chain with no extra work here."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from untangle import ids
from untangle.ingest.decisions import DecisionRow, closes_numbers, make_decision
from untangle.ingest.git_history import CommitRecord, GitRepo
from untangle.ingest.github_api import PullRecord
from untangle.ingest.symbols import (
    config_format,
    is_noisy_config,
    manifest_ecosystem,
    parse_config,
    parse_dependencies,
    should_skip,
)

log = logging.getLogger("untangle.ingest.config_history")

MAX_COMMITS_PER_FILE = 250
MAX_CHANGES_PER_VERSION = 150  # a reformat that rewrites everything is not 300 decisions


@dataclass(slots=True)
class KeyState:
    """Latest known state of a config key or dependency, for the ConfigKey / Dependency node."""

    path: str
    key: str
    value: str | None  # None once removed
    since: int
    ecosystem: str | None = None  # dependencies only


@dataclass(slots=True)
class ConfigHistory:
    decisions: list[DecisionRow]
    config_keys: dict[tuple[str, str], KeyState]  # (path, key)
    dependencies: dict[tuple[str, str], KeyState]  # (path, name)
    files_walked: int = 0
    versions_read: int = 0


def history_paths(all_paths: Iterable[str]) -> list[str]:
    """Config files and manifests worth walking (translations, fixtures, vendored and huge files excluded)."""
    out = []
    for path in all_paths:
        if should_skip(path) or is_noisy_config(path):
            continue
        if config_format(path) is not None or manifest_ecosystem(path) is not None:
            out.append(path)
    return out


def _version_values(path: str, text: str | None) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """`(config values, {dep name: (ecosystem, version)})` for one version of a file."""
    if text is None:
        return {}, {}
    deps = {d.name: (d.ecosystem, d.version or "*") for d in parse_dependencies(path, text)}
    values = parse_config(path, text) if manifest_ecosystem(path) is None else {}
    return values, deps


def _rationale(commit: CommitRecord, pr: PullRecord | None) -> str:
    text = commit.title.strip()
    if pr is not None and pr.title.strip() and pr.title.strip().lower() not in text.lower():
        text = f"{text} (PR #{pr.number}: {pr.title.strip()})"
    return text


def _link_common(row: DecisionRow, repo: str, commit: CommitRecord, pr: PullRecord | None, person_id: str, issue_numbers: set[int]) -> None:
    row.link("IMPLEMENTED_BY", ids.commit_id(repo, commit.sha))
    row.link("DECIDED_IN", ids.pr_id(repo, pr.number) if pr is not None else ids.commit_id(repo, commit.sha))
    row.link("STATED_BY", person_id)
    for n in closes_numbers(pr.body if pr is not None else None) + closes_numbers(commit.message):
        if n in issue_numbers:
            row.link("MOTIVATED_BY", ids.issue_id(repo, n))


def config_history(
    repo: str,
    git: GitRepo,
    commits: list[CommitRecord],
    paths: Iterable[str],
    *,
    pr_by_sha: dict[str, PullRecord] | None = None,
    person_id_for_email: dict[str, str] | None = None,
    issue_numbers: set[int] | None = None,
    max_commits_per_file: int = MAX_COMMITS_PER_FILE,
) -> ConfigHistory:
    """`commits` is the ingested history as `git log` returns it (newest first); only those commits are walked, so
    `--max-commits` and `--since` bound the work. The walk follows git's order reversed (topological, not the author
    timestamp), and each row carries that position as `order` so same-second commits still chain correctly."""
    pr_by_sha = pr_by_sha or {}
    person_id_for_email = person_id_for_email or {}
    issue_numbers = issue_numbers or set()
    wanted = set(paths)
    touches: dict[str, list[CommitRecord]] = {}
    position: dict[str, int] = {}
    for commit in reversed(list(commits)):
        position[commit.sha] = len(position)
        for fc in commit.files:
            if fc.path in wanted:
                touches.setdefault(fc.path, []).append(commit)
    result = ConfigHistory([], {}, {})
    for path, path_commits in sorted(touches.items()):
        if len(path_commits) > max_commits_per_file:
            log.info("skipping %s: touched by %d commits (> %d)", path, len(path_commits), max_commits_per_file)
            continue
        versions = git.show_many([(c.sha, path) for c in path_commits])
        result.files_walked += 1
        result.versions_read += len(versions)
        prev_values: dict[str, str] = {}
        prev_deps: dict[str, tuple[str, str]] = {}
        for commit in path_commits:
            text = versions.get((commit.sha, path))
            values, deps = _version_values(path, text)
            if text is None and not prev_values and not prev_deps:
                continue  # binary / oversize / unparsable from the start: nothing to say
            pr = pr_by_sha.get(commit.sha)
            person = person_id_for_email.get(commit.author_email, ids.person_id(email=commit.author_email))
            rationale = _rationale(commit, pr)
            changed = [(k, v) for k, v in values.items() if prev_values.get(k) != v]
            removed = [k for k in prev_values if k not in values]
            if len(changed) + len(removed) > MAX_CHANGES_PER_VERSION:
                log.debug("%s@%s: %d changes, keeping the first %d", path, commit.sha[:8], len(changed) + len(removed), MAX_CHANGES_PER_VERSION)
                changed, removed = changed[:MAX_CHANGES_PER_VERSION], removed[: max(0, MAX_CHANGES_PER_VERSION - len(changed))]
            for key, value in changed:
                row = make_decision(
                    repo, "config_value", f"{path}::{key}|config_value", commit.sha,
                    subject=f"{path}::{key}", predicate="config_value", object=value,
                    text=f"`{key}` in `{path}` is `{value}`", rationale=rationale, valid_from=commit.authored_at,
                    confidence=0.95, signal="config_diff",
                )
                row.link("ABOUT", ids.config_key_id(repo, path, key))
                row.link("ABOUT", ids.file_id(repo, path))
                _link_common(row, repo, commit, pr, person, issue_numbers)
                row.order = position[commit.sha]
                result.decisions.append(row)
                result.config_keys[(path, key)] = KeyState(path, key, value, commit.authored_at)
            for key in removed:
                row = make_decision(
                    repo, "config_value", f"{path}::{key}|config_value", commit.sha,
                    subject=f"{path}::{key}", predicate="config_value", object="removed",
                    text=f"`{key}` was removed from `{path}`", rationale=rationale, valid_from=commit.authored_at,
                    confidence=0.95, signal="config_diff",
                )
                row.link("ABOUT", ids.config_key_id(repo, path, key))
                row.link("ABOUT", ids.file_id(repo, path))
                _link_common(row, repo, commit, pr, person, issue_numbers)
                row.order = position[commit.sha]
                result.decisions.append(row)
                result.config_keys[(path, key)] = KeyState(path, key, None, commit.authored_at)
            for name, (eco, version) in deps.items():
                old = prev_deps.get(name)
                if old is not None and old[1] == version:
                    continue
                verb = "was added at" if old is None else "is at"
                row = make_decision(
                    repo, "dependency", f"dep|{name}|dependency_version", f"{commit.sha}:{path}",
                    subject=name, predicate="dependency_version", object=version,
                    text=f"`{name}` ({eco}) {verb} `{version}` in `{path}`", rationale=rationale, valid_from=commit.authored_at,
                    confidence=0.95, signal="lockfile_diff",
                )
                row.link("ABOUT", ids.dependency_id(repo, eco, name))
                row.link("ABOUT", ids.file_id(repo, path))
                _link_common(row, repo, commit, pr, person, issue_numbers)
                row.order = position[commit.sha]
                result.decisions.append(row)
                result.dependencies[(path, name)] = KeyState(path, name, version, commit.authored_at, eco)
            for name, (eco, _version) in prev_deps.items():
                if name in deps:
                    continue
                row = make_decision(
                    repo, "dependency", f"dep|{name}|dependency_version", f"{commit.sha}:{path}",
                    subject=name, predicate="dependency_version", object="removed",
                    text=f"`{name}` ({eco}) was removed from `{path}`", rationale=rationale, valid_from=commit.authored_at,
                    confidence=0.95, signal="lockfile_diff",
                )
                row.link("ABOUT", ids.dependency_id(repo, eco, name))
                row.link("ABOUT", ids.file_id(repo, path))
                _link_common(row, repo, commit, pr, person, issue_numbers)
                row.order = position[commit.sha]
                result.decisions.append(row)
                result.dependencies[(path, name)] = KeyState(path, name, None, commit.authored_at, eco)
            prev_values, prev_deps = values, deps
    result.decisions.sort(key=lambda r: (r.valid_from, r.order, r.id))
    return result


__all__ = ["ConfigHistory", "KeyState", "config_history", "history_paths"]
