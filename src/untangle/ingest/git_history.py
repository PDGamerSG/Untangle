"""Clone or fetch a GitHub repository and read its history with plain `git` plumbing.

Clones are untrusted data: nothing in them is ever executed or imported. Everything is read through
`git log`, `git ls-tree` and `git cat-file --batch`, so the clone is made with `--no-checkout` and no working
tree exists at all. Commit messages and file contents are decoded as UTF-8 with replacement."""

from __future__ import annotations

import logging
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from untangle.config import settings

log = logging.getLogger("untangle.ingest.git")

_RS, _US = "\x1e", "\x1f"
_LOG_FORMAT = f"format:{_RS}%H{_US}%P{_US}%an{_US}%ae{_US}%cn{_US}%ce{_US}%at{_US}%ct{_US}%s{_US}%B{_US}"
_RAW_LINE = re.compile(r"^:(\d{6}) (\d{6}) ([0-9a-f]+) ([0-9a-f]+) ([A-Z])(\d*)\t(.+)$")
_NUMSTAT_LINE = re.compile(r"^(\d+|-)\t(\d+|-)\t(.+)$")
_RENAME_BRACES = re.compile(r"\{([^{}]*) => ([^{}]*)\}")
_REVERTS_SHA = re.compile(r"This reverts commit ([0-9a-f]{7,40})", re.IGNORECASE)
_LS_TREE = re.compile(r"^(\d{6}) (\w+) ([0-9a-f]+) +(-|\d+)\t(.*)$")
_C_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "a": "\a", "b": "\b", "f": "\f", "r": "\r", "v": "\v"}

MAX_BLOB_BYTES = 400 * 1024


class GitError(RuntimeError):
    """A git command failed; the message carries stderr."""


@dataclass(slots=True)
class FileChange:
    path: str
    change: str  # 'A' | 'M' | 'D' | 'R'
    additions: int | None = None  # None for binary files (numstat prints '-')
    deletions: int | None = None
    old_path: str | None = None  # set when change == 'R'

    @property
    def binary(self) -> bool:
        return self.additions is None and self.deletions is None


@dataclass(slots=True)
class CommitRecord:
    sha: str
    parents: list[str]
    title: str
    message: str
    author_name: str
    author_email: str
    committer_name: str
    committer_email: str
    authored_at: int  # epoch ms
    committed_at: int
    is_merge: bool
    is_revert: bool
    reverts_sha: str | None
    files: list[FileChange] = field(default_factory=list)

    @property
    def additions(self) -> int:
        return sum(f.additions or 0 for f in self.files)

    @property
    def deletions(self) -> int:
        return sum(f.deletions or 0 for f in self.files)

    @property
    def files_changed(self) -> int:
        return len(self.files)


def _unquote(path: str) -> str:
    """git quotes paths with control characters or quotes as C strings even with core.quotepath=false."""
    if len(path) < 2 or not (path.startswith('"') and path.endswith('"')):
        return path
    out: list[str] = []
    body, i = path[1:-1], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in _C_ESCAPES:
                out.append(_C_ESCAPES[nxt])
                i += 2
                continue
            if nxt.isdigit():  # octal byte(s): gather consecutive escapes into one UTF-8 sequence
                raw = bytearray()
                while i + 3 < len(body) + 1 and body[i] == "\\" and body[i + 1 : i + 4].isdigit():
                    raw.append(int(body[i + 1 : i + 4], 8))
                    i += 4
                out.append(raw.decode("utf-8", errors="replace"))
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _numstat_path(path: str) -> str:
    """`dir/{old => new}/f`, `{ => new}/f` and `old => new` all resolve to the new path."""
    if "{" in path and " => " in path:
        resolved = _RENAME_BRACES.sub(r"\2", path)
        while "//" in resolved:
            resolved = resolved.replace("//", "/")
        return resolved.lstrip("/")
    if " => " in path:
        return path.split(" => ", 1)[1]
    return path


def detect_revert(message: str) -> tuple[bool, str | None]:
    """`(is_revert, reverted sha)` from a commit message."""
    m = _REVERTS_SHA.search(message or "")
    if m:
        return True, m.group(1)
    if (message or "").lstrip().startswith('Revert "'):
        return True, None
    return False, None


def parse_log(text: str) -> list[CommitRecord]:
    """Parse the output of `git log` run with the module's format plus `--raw --numstat -M`. Pure, for tests."""
    commits: list[CommitRecord] = []
    for record in text.split(_RS):
        if not record.strip():
            continue
        parts = record.split(_US)
        if len(parts) < 11:
            log.warning("skipping malformed git log record: %r", record[:80])
            continue
        sha, parents, an, ae, cn, ce, at, ct, subject, body = parts[:10]
        tail = _US.join(parts[10:])
        changes: dict[str, FileChange] = {}
        order: list[str] = []
        for line in tail.splitlines():
            raw = _RAW_LINE.match(line)
            if raw:
                kind, paths = raw.group(5), raw.group(7).split("\t")
                if kind in ("R", "C") and len(paths) >= 2:
                    old, new = _unquote(paths[0]), _unquote(paths[1])
                    fc = FileChange(new, "R" if kind == "R" else "A", old_path=old if kind == "R" else None)
                else:
                    new = _unquote(paths[-1])
                    fc = FileChange(new, {"A": "A", "D": "D"}.get(kind, "M"))  # T (type change) and friends → M
                if fc.path not in changes:
                    order.append(fc.path)
                changes[fc.path] = fc
                continue
            ns = _NUMSTAT_LINE.match(line)
            if ns:
                adds, dels, p = ns.groups()
                path = _unquote(_numstat_path(p))
                fc = changes.get(path)
                if fc is None:
                    fc = FileChange(path, "M")
                    changes[path] = fc
                    order.append(path)
                fc.additions = None if adds == "-" else int(adds)
                fc.deletions = None if dels == "-" else int(dels)
        message = body.strip("\n")
        is_revert, reverts_sha = detect_revert(message)
        parent_list = parents.split() if parents.strip() else []
        title = subject.strip() or (message.splitlines()[0] if message else "")
        commits.append(
            CommitRecord(
                sha=sha.strip(),
                parents=parent_list,
                title=title[:500],
                message=message,
                author_name=an.strip(),
                author_email=ae.strip().lower(),
                committer_name=cn.strip(),
                committer_email=ce.strip().lower(),
                authored_at=int(at) * 1000,
                committed_at=int(ct) * 1000,
                is_merge=len(parent_list) > 1,
                is_revert=is_revert,
                reverts_sha=reverts_sha,
                files=[changes[p] for p in order],
            )
        )
    return commits


class GitRepo:
    """A local git directory. All reads go through git itself, never through a working tree."""

    def __init__(self, path: Path):
        self.path = Path(path)

    # -- plumbing -------------------------------------------------------------------------------
    def _run(self, args: list[str], *, input_bytes: bytes | None = None, check: bool = True) -> bytes:
        cmd = ["git", "-c", "core.quotepath=false", "-c", "core.longpaths=true", "-C", str(self.path), *args]
        proc = subprocess.run(cmd, input=input_bytes, capture_output=True, check=False)
        if check and proc.returncode != 0:
            err = proc.stderr.decode("utf-8", "replace").strip()[:400]
            raise GitError(f"git {' '.join(args[:2])} failed ({proc.returncode}): {err}")
        return proc.stdout

    def git(self, *args: str, check: bool = True) -> str:
        return self._run(list(args), check=check).decode("utf-8", errors="replace")

    def is_repo(self) -> bool:
        return (self.path / ".git").exists() or (self.path / "HEAD").is_file()

    def default_branch(self) -> str:
        out = self.git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False).strip()
        if out.startswith("origin/"):
            return out[len("origin/") :]
        out = self.git("symbolic-ref", "--short", "HEAD", check=False).strip()
        return out or "HEAD"

    def head_sha(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    # -- history --------------------------------------------------------------------------------
    def log(self, *, since: str | None = None, max_commits: int | None = None, rev: str = "HEAD") -> list[CommitRecord]:
        """Commits reachable from `rev`, newest first, with change types, renames and line counts per file."""
        args = ["log", rev, f"--format={_LOG_FORMAT}", "--raw", "--numstat", "-M", "--no-color"]
        if since:
            args.append(f"--since={since}")
        if max_commits:
            args.append(f"-n{int(max_commits)}")
        return parse_log(self.git(*args))

    def files_at_head(self, rev: str = "HEAD") -> dict[str, int]:
        """`path -> size in bytes` for regular files at `rev` (symlinks and submodules are skipped)."""
        files: dict[str, int] = {}
        for line in self.git("ls-tree", "-r", "-l", "--full-tree", rev).splitlines():
            m = _LS_TREE.match(line)
            if not m:
                continue
            mode, kind, _obj, size, path = m.groups()
            if kind != "blob" or mode == "120000":
                continue
            files[_unquote(path)] = int(size) if size != "-" else 0
        return files

    def show(self, sha: str, path: str) -> str | None:
        """Decoded content of `path` at `sha`, or None when it does not exist there."""
        return self.show_many([(sha, path)]).get((sha, path))

    def show_many(self, pairs: Iterable[tuple[str, str]], *, max_bytes: int = MAX_BLOB_BYTES) -> dict[tuple[str, str], str | None]:
        """One `git cat-file --batch` call over many `sha:path` names. Missing objects and blobs larger than
        `max_bytes` map to None (big blobs are never interesting for text extraction)."""
        wanted = list(dict.fromkeys(pairs))
        out: dict[tuple[str, str], str | None] = {}
        if not wanted:
            return out
        request = "".join(f"{sha}:{path}\n" for sha, path in wanted).encode("utf-8", errors="replace")
        data = self._run(["cat-file", "--batch"], input_bytes=request)
        pos, i = 0, 0
        while i < len(wanted) and pos < len(data):
            nl = data.find(b"\n", pos)
            if nl < 0:
                break
            header = data[pos:nl].decode("utf-8", errors="replace")
            pos = nl + 1
            key = wanted[i]
            i += 1
            if header.endswith(" missing") or header.endswith(" ambiguous"):
                out[key] = None
                continue
            try:
                size = int(header.rsplit(" ", 1)[1])
            except (IndexError, ValueError):
                out[key] = None
                continue
            blob = data[pos : pos + size]
            pos += size + 1  # trailing newline after the object body
            out[key] = None if size > max_bytes else blob.decode("utf-8", errors="replace")
        for key in wanted[i:]:
            out.setdefault(key, None)
        return out

    def read_at(self, paths: Iterable[str], rev: str = "HEAD", *, max_bytes: int = MAX_BLOB_BYTES) -> dict[str, str]:
        """`path -> text` for the paths that exist at `rev` and are small enough."""
        content = self.show_many([(rev, p) for p in paths], max_bytes=max_bytes)
        return {p: text for (_, p), text in content.items() if text is not None}


def repo_dir(full_name: str, cache_dir: Path | None = None) -> Path:
    owner, name = full_name.split("/", 1)
    return (cache_dir or settings().repo_cache) / owner / name


def clone_or_fetch(full_name: str, cache_dir: Path | None = None, *, url: str | None = None) -> GitRepo:
    """Clone `https://github.com/<full_name>.git` into the cache without a working tree, or fetch when present."""
    target = repo_dir(full_name, cache_dir)
    repo = GitRepo(target)
    url = url or f"https://github.com/{full_name}.git"
    if repo.is_repo():
        log.info("fetching %s", full_name)
        repo.git("fetch", "--quiet", "--prune", "origin")
        branch = repo.default_branch()
        if branch != "HEAD":
            repo.git("update-ref", f"refs/heads/{branch}", f"refs/remotes/origin/{branch}")
            repo.git("symbolic-ref", "HEAD", f"refs/heads/{branch}")
        return repo
    target.parent.mkdir(parents=True, exist_ok=True)
    log.info("cloning %s into %s", full_name, target)
    proc = subprocess.run(
        ["git", "clone", "--quiet", "--no-checkout", "--single-branch", url, str(target)], capture_output=True, check=False
    )
    if proc.returncode != 0:
        raise GitError(f"git clone {full_name} failed: {proc.stderr.decode('utf-8', 'replace').strip()[:400]}")
    return repo


__all__ = ["CommitRecord", "FileChange", "GitError", "GitRepo", "clone_or_fetch", "detect_revert", "parse_log", "repo_dir"]
