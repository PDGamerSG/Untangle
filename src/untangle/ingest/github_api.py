"""GitHub REST client for pull requests, reviews, review comments, conversation comments, PR commits and issues.

Every response body is cached as JSON under `.cache/github/<owner>/<name>/`, so a second run of the same
ingestion costs no API calls and tests replay recorded fixtures through `respx` or an injected transport.
Authentication: an explicit token, else `GITHUB_TOKEN` from settings, else `gh auth token`, else anonymous
(60 requests/hour; the client sleeps until `X-RateLimit-Reset` when the limit hits)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from untangle.config import PROJECT_ROOT, settings

log = logging.getLogger("untangle.ingest.github")

API = "https://api.github.com"
PER_PAGE = 100
MAX_PAGES = 100
MAX_COMMENTS_PER_PR = 100
MAX_COMMENTS_PER_ISSUE = 50
MAX_WAIT_SECONDS = 3600

_INCIDENT_LABEL = re.compile(r"bug|incident|regression|outage|hotfix|security|crash|data.?loss|urgent", re.IGNORECASE)
_INCIDENT_TITLE = re.compile(r"\b(crash(?:es|ed|ing)?|panic(?:s|ked)?|outage|regression|data loss|hotfix)\b", re.IGNORECASE)
_SAFE = re.compile(r"[^A-Za-z0-9._=-]+")


class GitHubError(RuntimeError):
    """A request failed for good (bad credentials, repeated 5xx, rate limit wait too long)."""


# -- records -----------------------------------------------------------------------------------------
@dataclass(slots=True)
class CommentRecord:
    id: int
    kind: str  # pr_review | pr_review_comment | pr_comment | issue_comment
    author_login: str | None
    body: str
    created_at: int | None
    url: str | None
    path: str | None = None
    line: int | None = None
    review_state: str | None = None


@dataclass(slots=True)
class ReviewRecord:
    id: int
    author_login: str | None
    state: str  # APPROVED | CHANGES_REQUESTED | COMMENTED | DISMISSED | PENDING
    body: str
    submitted_at: int | None
    url: str | None


@dataclass(slots=True)
class PRCommitRecord:
    sha: str
    author_name: str | None
    author_email: str | None
    author_login: str | None
    message: str


@dataclass(slots=True)
class PullRecord:
    number: int
    title: str
    body: str
    state: str
    merged: bool
    created_at: int | None
    updated_at: int | None
    merged_at: int | None
    closed_at: int | None
    url: str
    author_login: str | None
    labels: list[str]
    merge_commit_sha: str | None
    head_sha: str | None
    reviews: list[ReviewRecord] = field(default_factory=list)
    review_comments: list[CommentRecord] = field(default_factory=list)
    comments: list[CommentRecord] = field(default_factory=list)
    commits: list[PRCommitRecord] = field(default_factory=list)

    @property
    def discussion_size(self) -> int:
        return len(self.reviews) + len(self.review_comments) + len(self.comments)


@dataclass(slots=True)
class IssueRecord:
    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    created_at: int | None
    closed_at: int | None
    url: str
    author_login: str | None
    is_incident: bool
    comments_count: int = 0
    comments: list[CommentRecord] = field(default_factory=list)


@dataclass(slots=True)
class GitHubData:
    prs: list[PullRecord] = field(default_factory=list)
    issues: list[IssueRecord] = field(default_factory=list)
    pr_numbers: set[int] = field(default_factory=set)
    email_to_login: dict[str, str] = field(default_factory=dict)
    login_names: dict[str, str] = field(default_factory=dict)
    requests_made: int = 0
    cache_hits: int = 0


# -- helpers -------------------------------------------------------------------------------------------
def to_ms(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def is_incident(title: str, labels: list[str]) -> bool:
    return any(_INCIDENT_LABEL.search(label or "") for label in labels) or bool(_INCIDENT_TITLE.search(title or ""))


def resolve_token(explicit: str | None = None) -> str | None:
    """Explicit token, else settings, else `gh auth token`, else None (anonymous)."""
    if explicit:
        return explicit
    if settings().github_token:
        return settings().github_token
    gh = shutil.which("gh")
    if gh:
        try:
            proc = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=15, check=False)
            token = proc.stdout.strip()
            if proc.returncode == 0 and token:
                return token
        except (OSError, subprocess.SubprocessError) as exc:
            log.debug("gh auth token failed: %s", exc)
    return None


def github_cache_dir(full_name: str) -> Path:
    owner, name = full_name.split("/", 1)
    return PROJECT_ROOT / ".cache" / "github" / owner / name


def _login(obj: dict | None) -> str | None:
    if not obj:
        return None
    user = obj.get("user") if "user" in obj else obj
    return (user or {}).get("login") if isinstance(user, dict) else None


def _labels(obj: dict) -> list[str]:
    return [lab.get("name", "") if isinstance(lab, dict) else str(lab) for lab in obj.get("labels") or []]


# -- client --------------------------------------------------------------------------------------------
class GitHubClient:
    """Thread-safe (httpx.Client has a pool). `transport` and `sleep` are injectable for tests."""

    def __init__(
        self,
        full_name: str,
        *,
        token: str | None | bool = True,
        cache_dir: Path | None = None,
        transport: httpx.BaseTransport | None = None,
        workers: int = 4,
        base_url: str = API,
        sleep: Callable[[float], None] = time.sleep,
        use_cache: bool = True,
    ):
        self.full_name = full_name
        self.owner, self.name = full_name.split("/", 1)
        self.token = resolve_token(None if token is True else token) if token is not False else None
        self.cache_dir = cache_dir if cache_dir is not None else github_cache_dir(full_name)
        self.use_cache = use_cache
        self.workers = max(1, workers)
        self.base_url = base_url.rstrip("/")
        self._sleep = sleep
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "untangle-ingest/0.1"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.Client(headers=headers, timeout=httpx.Timeout(30.0), transport=transport, follow_redirects=True)
        self._lock = threading.Lock()
        self.requests_made = 0
        self.cache_hits = 0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- cache ------------------------------------------------------------------------------------------
    def _cache_path(self, path: str, params: dict[str, Any]) -> Path:
        query = urlencode(sorted((k, str(v)) for k, v in params.items()))
        short = path.removeprefix(f"repos/{self.owner}/{self.name}/")
        stem = _SAFE.sub("_", f"{short}_{query}").strip("_")[:120]
        digest = hashlib.sha1(f"{path}?{query}".encode()).hexdigest()[:10]
        return self.cache_dir / f"{stem}-{digest}.json"

    def _cache_read(self, cache_path: Path) -> Any:
        try:
            with cache_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def _cache_write(self, cache_path: Path, payload: Any) -> None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_suffix(f".{threading.get_ident()}.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            tmp.replace(cache_path)
        except OSError as exc:  # a cache failure must never fail the ingestion
            log.warning("could not cache %s: %s", cache_path.name, exc)

    # -- requests ---------------------------------------------------------------------------------------
    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """JSON body of `GET /<path>` (cached). A 404 yields None; rate limits sleep; 5xx and transport
        errors retry with backoff; anything else raises `GitHubError`."""
        params = params or {}
        cache_path = self._cache_path(path, params)
        if self.use_cache and cache_path.is_file():
            cached = self._cache_read(cache_path)
            if cached is not None:
                with self._lock:
                    self.cache_hits += 1
                return cached.get("body") if isinstance(cached, dict) and "body" in cached else cached
        payload = self._request(path, params)
        if self.use_cache:
            self._cache_write(cache_path, {"path": path, "params": params, "fetched_at": int(time.time()), "body": payload})
        return payload

    def _request(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        waited = 0.0
        for attempt in range(8):
            try:
                resp = self._client.get(url, params=params)
            except httpx.TransportError as exc:
                delay = min(2.0**attempt, 30.0)
                log.warning("GET %s: %s; retrying in %.0fs", path, exc, delay)
                self._sleep(delay)
                continue
            with self._lock:
                self.requests_made += 1
            status = resp.status_code
            if status == 200:
                return resp.json()
            if status == 404:
                return None
            if status in (403, 429):
                delay = self._rate_limit_delay(resp, attempt)
                if delay is None:
                    raise GitHubError(f"GET {path} forbidden: {resp.text[:200]}")
                waited += delay
                if waited > MAX_WAIT_SECONDS:
                    raise GitHubError(f"GET {path}: rate limit wait exceeds {MAX_WAIT_SECONDS}s")
                log.warning("GitHub rate limit hit on %s; sleeping %.0fs", path, delay)
                self._sleep(delay)
                continue
            if status == 401:
                raise GitHubError("GitHub rejected the token (401); unset GITHUB_TOKEN or run `gh auth login`")
            if status >= 500 or status == 408:
                delay = min(2.0**attempt, 30.0)
                log.warning("GET %s -> %s; retrying in %.0fs", path, status, delay)
                self._sleep(delay)
                continue
            if status in (410, 422, 451):  # gone / validation / legal block: treat like missing
                return None
            raise GitHubError(f"GET {path} -> {status}: {resp.text[:200]}")
        raise GitHubError(f"GET {path}: gave up after retries")

    @staticmethod
    def _rate_limit_delay(resp: httpx.Response, attempt: int) -> float | None:
        retry_after = resp.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return float(retry_after) + 1
        if resp.headers.get("X-RateLimit-Remaining") == "0":
            reset = resp.headers.get("X-RateLimit-Reset")
            if reset and reset.isdigit():
                return max(1.0, float(reset) - time.time() + 2)
            return 60.0
        body = resp.text.lower()
        if "rate limit" in body or "abuse" in body or resp.status_code == 429:
            return min(30.0 * (2**attempt), 600.0)
        return None  # a real 403 (private repo, missing scope)

    def paginate(self, path: str, params: dict[str, Any] | None = None, *, max_items: int | None = None) -> list[Any]:
        items: list[Any] = []
        params = dict(params or {})
        params.setdefault("per_page", PER_PAGE)
        for page in range(1, MAX_PAGES + 1):
            batch = self.get(path, {**params, "page": page})
            if not batch or not isinstance(batch, list):
                break
            items.extend(batch)
            if len(batch) < params["per_page"] or (max_items is not None and len(items) >= max_items):
                break
        return items[:max_items] if max_items is not None else items

    # -- endpoints --------------------------------------------------------------------------------------
    def _repo(self, suffix: str) -> str:
        return f"repos/{self.owner}/{self.name}/{suffix}"

    def pulls(self, max_prs: int | None = None) -> list[PullRecord]:
        """PRs sorted by last update, newest first, without their discussion (see `enrich_pull`)."""
        raw = self.paginate(self._repo("pulls"), {"state": "all", "sort": "updated", "direction": "desc"}, max_items=max_prs)
        return [self._pull(obj) for obj in raw if isinstance(obj, dict) and obj.get("number")]

    @staticmethod
    def _pull(obj: dict) -> PullRecord:
        return PullRecord(
            number=int(obj["number"]), title=obj.get("title") or "", body=obj.get("body") or "", state=obj.get("state") or "open",
            merged=bool(obj.get("merged_at")), created_at=to_ms(obj.get("created_at")), updated_at=to_ms(obj.get("updated_at")),
            merged_at=to_ms(obj.get("merged_at")), closed_at=to_ms(obj.get("closed_at")), url=obj.get("html_url") or "",
            author_login=_login(obj), labels=_labels(obj), merge_commit_sha=obj.get("merge_commit_sha"),
            head_sha=(obj.get("head") or {}).get("sha"),
        )

    def enrich_pull(self, pr: PullRecord) -> PullRecord:
        n = pr.number
        pr.reviews = [
            ReviewRecord(int(r["id"]), _login(r), r.get("state") or "COMMENTED", r.get("body") or "", to_ms(r.get("submitted_at")), r.get("html_url"))
            for r in self.paginate(self._repo(f"pulls/{n}/reviews"), max_items=MAX_COMMENTS_PER_PR)
            if isinstance(r, dict) and r.get("id")
        ]
        pr.review_comments = [
            CommentRecord(int(c["id"]), "pr_review_comment", _login(c), c.get("body") or "", to_ms(c.get("created_at")), c.get("html_url"),
                          path=c.get("path"), line=c.get("line") or c.get("original_line"))
            for c in self.paginate(self._repo(f"pulls/{n}/comments"), max_items=MAX_COMMENTS_PER_PR)
            if isinstance(c, dict) and c.get("id")
        ]
        pr.comments = [
            CommentRecord(int(c["id"]), "pr_comment", _login(c), c.get("body") or "", to_ms(c.get("created_at")), c.get("html_url"))
            for c in self.paginate(self._repo(f"issues/{n}/comments"), max_items=MAX_COMMENTS_PER_PR)
            if isinstance(c, dict) and c.get("id")
        ]
        pr.commits = [
            PRCommitRecord(
                c["sha"], ((c.get("commit") or {}).get("author") or {}).get("name"),
                (((c.get("commit") or {}).get("author") or {}).get("email") or "").lower() or None,
                _login(c.get("author")) if isinstance(c.get("author"), dict) else None, (c.get("commit") or {}).get("message") or "",
            )
            for c in self.paginate(self._repo(f"pulls/{n}/commits"), max_items=250)
            if isinstance(c, dict) and c.get("sha")
        ]
        return pr

    def issues(self) -> tuple[list[IssueRecord], set[int]]:
        """Real issues (entries carrying `pull_request` are PRs and only contribute their numbers)."""
        issues: list[IssueRecord] = []
        pr_numbers: set[int] = set()
        for obj in self.paginate(self._repo("issues"), {"state": "all", "sort": "created", "direction": "desc"}):
            if not isinstance(obj, dict) or not obj.get("number"):
                continue
            if "pull_request" in obj:
                pr_numbers.add(int(obj["number"]))
                continue
            labels = _labels(obj)
            issues.append(
                IssueRecord(
                    number=int(obj["number"]), title=obj.get("title") or "", body=obj.get("body") or "", state=obj.get("state") or "open",
                    labels=labels, created_at=to_ms(obj.get("created_at")), closed_at=to_ms(obj.get("closed_at")),
                    url=obj.get("html_url") or "", author_login=_login(obj), is_incident=is_incident(obj.get("title") or "", labels),
                    comments_count=int(obj.get("comments") or 0),
                )
            )
        return issues, pr_numbers

    def issue_comments(self, issue: IssueRecord) -> list[CommentRecord]:
        return [
            CommentRecord(int(c["id"]), "issue_comment", _login(c), c.get("body") or "", to_ms(c.get("created_at")), c.get("html_url"))
            for c in self.paginate(self._repo(f"issues/{issue.number}/comments"), max_items=MAX_COMMENTS_PER_ISSUE)
            if isinstance(c, dict) and c.get("id")
        ]

    # -- orchestration ----------------------------------------------------------------------------------
    def fetch_all(
        self,
        *,
        max_prs: int | None = None,
        issue_comments: str = "incidents",
        progress: Callable[[str], None] | None = None,
    ) -> GitHubData:
        """PRs with discussion and commits, issues (comments for incidents by default: `all` | `incidents` | `none`)."""
        say = progress or (lambda msg: log.info(msg))
        data = GitHubData()
        data.prs = self.pulls(max_prs)
        say(f"github: {len(data.prs)} pull requests listed ({'token' if self.token else 'anonymous'})")
        done = 0

        def enrich(pr: PullRecord) -> PullRecord:
            try:
                return self.enrich_pull(pr)
            except GitHubError as exc:
                log.warning("PR #%s: %s", pr.number, exc)
                return pr

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for pr in pool.map(enrich, data.prs):
                done += 1
                if done % 100 == 0:
                    say(f"github: {done}/{len(data.prs)} pull requests fetched")
                for c in pr.commits:
                    if c.author_email and c.author_login:
                        data.email_to_login.setdefault(c.author_email, c.author_login)
                        if c.author_name:
                            data.login_names.setdefault(c.author_login, c.author_name)
        data.issues, data.pr_numbers = self.issues()
        data.pr_numbers.update(pr.number for pr in data.prs)
        say(f"github: {len(data.issues)} issues ({sum(i.is_incident for i in data.issues)} incidents)")
        wanted = [i for i in data.issues if i.comments_count > 0 and (issue_comments == "all" or (issue_comments == "incidents" and i.is_incident))]
        if wanted:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                for issue, comments in zip(wanted, pool.map(self._safe_issue_comments, wanted), strict=True):
                    issue.comments = comments
        data.requests_made, data.cache_hits = self.requests_made, self.cache_hits
        say(f"github: {data.requests_made} requests, {data.cache_hits} cache hits")
        return data

    def _safe_issue_comments(self, issue: IssueRecord) -> list[CommentRecord]:
        try:
            return self.issue_comments(issue)
        except GitHubError as exc:
            log.warning("issue #%s comments: %s", issue.number, exc)
            return []


__all__ = [
    "CommentRecord", "GitHubClient", "GitHubData", "GitHubError", "IssueRecord", "PRCommitRecord", "PullRecord",
    "ReviewRecord", "github_cache_dir", "is_incident", "resolve_token", "to_ms",
]
