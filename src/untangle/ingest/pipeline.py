"""`ingest_repo(full_name, ...)`: the whole ingestion in one call, stage by stage, with timings and counts.

Order: clone/fetch → git log → GitHub (PRs, reviews, comments, issues) → people → files/modules → HEAD content
(symbols, config keys, dependencies, documents) → config and dependency history → deterministic decisions (config,
ADR, PR change, revert, explicit supersession) → optional LLM rationale → chunks + embeddings → graph writes
→ the Repo node last, so a run that died half-way is visible as such."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from untangle import ids
from untangle.embed import Embedder, make_embedder
from untangle.graph.db import Graph, connect
from untangle.ingest import chunks as chunking
from untangle.ingest import docs as documents
from untangle.ingest.config_history import config_history, history_paths
from untangle.ingest.decisions import DecisionRow, explicit_supersessions, pr_change_decisions, revert_decisions
from untangle.ingest.extract_llm import extract_pr_rationales
from untangle.ingest.git_history import GitRepo, clone_or_fetch
from untangle.ingest.github_api import GitHubClient, GitHubData, GitHubError
from untangle.ingest.loader import (
    Loader,
    People,
    commit_rows,
    config_key_rows,
    dependency_rows,
    document_rows,
    file_rows,
    github_rows,
    revert_rows,
    symbol_rows,
)
from untangle.ingest.symbols import (
    MAX_FILE_BYTES,
    config_format,
    extract_config_keys,
    extract_symbols,
    language_of,
    languages,
    manifest_ecosystem,
    parse_dependencies,
    should_skip,
)
from untangle.llm import LLM

log = logging.getLogger("untangle.ingest.pipeline")
Progress = Callable[[str], None]


class _Timer:
    def __init__(self, progress: Progress):
        self.progress = progress
        self.timings: dict[str, float] = {}
        self.started = time.perf_counter()
        self._stage_started = self.started
        self._stage: str | None = None

    def stage(self, name: str) -> None:
        self.end()
        self._stage, self._stage_started = name, time.perf_counter()

    def end(self, note: str = "") -> None:
        if self._stage is not None:
            dt = time.perf_counter() - self._stage_started
            self.timings[self._stage] = round(dt, 2)
            self.progress(f"[{self._stage}] {note + ' ' if note else ''}in {dt:.1f}s")
            self._stage = None

    @property
    def total(self) -> float:
        return round(time.perf_counter() - self.started, 2)


def ingest_repo(
    full_name: str,
    *,
    graph: Graph | None = None,
    since: str | None = None,
    max_commits: int | None = None,
    max_prs: int | None = None,
    github: bool = True,
    embed: bool = True,
    llm_prs: int = 0,
    reset: bool = False,
    progress: Progress = log.info,
    cache_dir: Path | None = None,
    repo_path: Path | None = None,
    github_client: GitHubClient | None = None,
    embedder: Embedder | None = None,
    llm: LLM | None = None,
    issue_comments: str = "incidents",
) -> dict[str, Any]:
    """Ingest `owner/name` into the graph and return a summary (counts, timings, `Graph.stats`).

    `repo_path` points at an existing local git directory instead of cloning (tests); `github_client`, `embedder`
    and `llm` are injectable for the same reason. `reset=True` wipes the repository from the graph first."""
    timer = _Timer(progress)
    repo = full_name
    own_graph = graph is None
    graph = graph or connect()
    try:
        if reset:
            timer.stage("reset")
            timer.end(f"deleted {graph.wipe_repo(repo)} nodes")

        # -- git ----------------------------------------------------------------------------------------
        timer.stage("git")
        git = GitRepo(repo_path) if repo_path else clone_or_fetch(full_name, cache_dir)
        commits = git.log(since=since, max_commits=max_commits)  # newest first
        head_sha, default_branch = git.head_sha(), git.default_branch()
        head_files = git.files_at_head()
        commits_by_sha = {c.sha: c for c in commits}
        timer.end(f"{len(commits)} commits, {len(head_files)} files at HEAD ({default_branch}@{head_sha[:8]})")

        # -- github -------------------------------------------------------------------------------------
        gh = GitHubData()
        if github:
            timer.stage("github")
            client = github_client or GitHubClient(full_name)
            try:
                gh = client.fetch_all(max_prs=max_prs, issue_comments=issue_comments, progress=progress)
            except GitHubError as exc:
                log.error("GitHub stage failed, continuing with git only: %s", exc)
            finally:
                if github_client is None:
                    client.close()
            timer.end(f"{len(gh.prs)} PRs, {len(gh.issues)} issues")

        # -- people, files ------------------------------------------------------------------------------
        timer.stage("rows")
        people = People(gh.email_to_login, gh.login_names)
        commit_rows_ = commit_rows(repo, commits, people)
        files = file_rows(repo, commits, head_files, people)
        gh_rows = github_rows(repo, gh, commits_by_sha, people)
        timer.end(f"{len(files.files)} files, {sum(len(m) for m in files.modules_by_depth)} modules, {len(people.persons)} people")

        # -- HEAD content: symbols, config keys, dependencies, documents ----------------------------------
        timer.stage("head")
        interesting = [p for p, size in head_files.items() if not should_skip(p, size) and size <= MAX_FILE_BYTES
                       and (language_of(p) or config_format(p) or manifest_ecosystem(p))]
        doc_paths = documents.select_doc_paths(head_files)
        content = git.read_at(sorted(set(interesting) | set(doc_paths)))
        symbols, head_keys, head_deps = [], [], []
        for path in interesting:
            text = content.get(path)
            if text is None:
                continue
            if language_of(path):
                syms, consts = extract_symbols(path, text)
                symbols.extend(syms)
                head_keys.extend(consts)
            if config_format(path):
                head_keys.extend(extract_config_keys(path, text))
            if manifest_ecosystem(path):
                head_deps.extend(parse_dependencies(path, text))
        docs = [documents.parse_document(p, content[p]) for p in doc_paths if p in content]
        documents.resolve_supersessions(docs)
        timer.end(f"{len(symbols)} symbols, {len(head_keys)} config keys, {len(head_deps)} dependencies, {len(docs)} documents")

        # -- config / dependency history ------------------------------------------------------------------
        timer.stage("history")
        touched_paths = {fc.path for c in commits for fc in c.files}
        hist = config_history(
            repo, git, commits, history_paths(touched_paths | set(head_files)), pr_by_sha=gh_rows.pr_by_sha,
            person_id_for_email=people.person_id_for_email, issue_numbers=gh_rows.issue_numbers,
        )
        timer.end(f"{hist.files_walked} files, {hist.versions_read} versions, {len(hist.decisions)} value changes")

        # -- decisions --------------------------------------------------------------------------------------
        timer.stage("decisions")
        decisions: list[DecisionRow] = list(hist.decisions)
        adr_rows = documents.adr_decisions(repo, docs, added_at=files.first_seen_at, added_by=files.first_author, known_paths=set(head_files))
        decisions.extend(adr_rows)
        change_rows = pr_change_decisions(
            repo, gh.prs, commits_by_sha, gh_rows.pr_commit_shas, gh_rows.issue_numbers, gh_rows.comment_ids_by_pr, people.person_id_for_login
        )
        explicit = explicit_supersessions(repo, gh.prs, {int(r.subject[3:]): r for r in change_rows})
        decisions.extend(change_rows)
        by_commit: dict[str, list[str]] = {}
        for row in decisions:
            for rel, target, _ in row.links:
                if rel == "IMPLEMENTED_BY":
                    by_commit.setdefault(target, []).append(row.id)
        reverts = revert_decisions(repo, commits, commits_by_sha, by_commit, people.person_id_for_email)
        decisions.extend(reverts)
        llm_rows: list[DecisionRow] = []
        if llm_prs > 0 and gh.prs:
            llm_rows = extract_pr_rationales(repo, gh.prs, top_n=llm_prs, llm=llm, known_paths=set(head_files), person_id_for_login=people.person_id_for_login)
            decisions.extend(llm_rows)
        timer.end(f"{len(hist.decisions)} config/dependency, {len(adr_rows)} adr, {len(change_rows)} change, {len(reverts)} revert, "
                  f"{explicit} explicit supersessions, {len(llm_rows)} llm")

        # -- chunks -----------------------------------------------------------------------------------------
        timer.stage("chunks")
        sources = chunking.build_sources(repo, commits=commits, prs=gh.prs, issues=gh.issues, documents=docs)
        chunk_rows = chunking.chunk_rows(repo, sources, embedder=(embedder or make_embedder()) if embed else None)
        timer.end(f"{len(chunk_rows)} chunks" + (" embedded" if embed else " (no embeddings)"))

        # -- write ------------------------------------------------------------------------------------------
        timer.stage("write")
        loader = Loader(graph, repo)
        n_people = loader.people(people)
        loader.write("11_upsert_commits", commit_rows_)
        file_counts = loader.files(files)
        loader.write("13_upsert_symbols", symbol_rows(repo, symbols))
        loader.write("13_upsert_config_keys", config_key_rows(repo, head_keys, hist.config_keys))
        loader.write("13_upsert_dependencies", dependency_rows(repo, head_deps, hist.dependencies))
        gh_counts = loader.github(gh_rows)
        doc_rows, doc_links = document_rows(repo, docs)
        loader.write("15_upsert_documents", doc_rows)
        loader.write("15_link_documents", doc_links)
        loader.write("17_upsert_reverts", revert_rows(repo, commits, commits_by_sha))
        decision_counts = loader.decisions(decisions)
        n_chunks = loader.chunks(chunk_rows)
        loader.repo_node({
            "id": ids.repo_id(repo), "full_name": repo, "url": f"https://github.com/{repo}", "default_branch": default_branch,
            "head_sha": head_sha, "ingested_at": int(time.time() * 1000), "commit_count": len(commits), "languages": languages(head_files),
        })
        timer.end(f"{n_people[0]} people, {len(commit_rows_)} commits, {file_counts['files']} files, {gh_counts['prs']} PRs, "
                  f"{decision_counts['recorded']} decisions ({decision_counts['superseded']} superseded), {n_chunks} chunks")

        stats = graph.stats(repo)
        summary = {
            "repo": repo, "head_sha": head_sha, "default_branch": default_branch, "commits": len(commits), "files": len(files.files),
            "prs": len(gh.prs), "issues": len(gh.issues), "people": len(people.persons), "symbols": len(symbols), "config_keys": len(head_keys),
            "dependencies": len(head_deps), "documents": len(docs), "decisions": decision_counts, "chunks": n_chunks,
            "github_requests": gh.requests_made, "github_cache_hits": gh.cache_hits, "timings": timer.timings, "total_seconds": timer.total,
            "stats": stats, "writes": loader.counts,
        }
        progress(f"ingested {repo}: {stats['nodes']} nodes, {stats['relationships']} relationships in {timer.total:.0f}s")
        return summary
    finally:
        if own_graph:
            graph.close()


__all__ = ["ingest_repo"]
