"""A small, deterministic git repository for the ingestion tests (built in `tmp_path`, no network).

History (author dates one month apart so ordering is unambiguous):
  c1 initial import        config/app.yaml, config.toml, go.mod, cmd/main.go, README.md, ADR-0001, logo.png (binary)
  c2 raise retry limit     app.yaml retry_limit 3 -> 5, config.toml concurrency 10 -> 20
  c3 switch to pgx (#7)    go.mod lib/pq v1.10.0 -> v1.10.9, ADR-0002 accepted, ADR-0001 superseded by ADR-0002
  c4 rename                cmd/main.go -> cmd/server.go
  c5 revert of c2          `git revert` (retry_limit back to 3, concurrency back to 10)
  c6 fix crash (#9)        cmd/server.go edited, message "Fixes #5"
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

AUTHOR = ("Ada Lovelace", "ada@example.com")
DATES = [
    "2024-01-01T10:00:00+00:00", "2024-02-01T10:00:00+00:00", "2024-03-01T10:00:00+00:00",
    "2024-04-01T10:00:00+00:00", "2024-05-01T10:00:00+00:00", "2024-06-01T10:00:00+00:00",
]
DATES_MS = [1704103200000, 1706781600000, 1709287200000, 1711965600000, 1714557600000, 1717236000000]

ADR_0001 = """# 1. Use Postgres

## Status

Accepted

## Date

2023-12-20

## Context

We need a relational store with JSON support.

## Decision

Use PostgreSQL through lib/pq.

## Consequences

One database to operate.
"""
ADR_0001_SUPERSEDED = ADR_0001.replace("Accepted", "Superseded by [ADR-0002](0002-switch-to-pgx.md)")
ADR_0002 = """---
title: "Switch to pgx"
status: accepted
date: 2024-03-01
---

## Context and Problem Statement

lib/pq is in maintenance mode.

## Decision Outcome

Use jackc/pgx for the connection pool in cmd/server.go.
"""


def git(path: Path, *args: str, date: str | None = None) -> str:
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": AUTHOR[0], "GIT_AUTHOR_EMAIL": AUTHOR[1], "GIT_COMMITTER_NAME": AUTHOR[0],
        "GIT_COMMITTER_EMAIL": AUTHOR[1], "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(path),
    })
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    proc = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", "-c", "core.quotepath=false", *args],
        cwd=path, env=env, check=True, capture_output=True,
    )
    return proc.stdout.decode("utf-8", "replace").strip()


def write(path: Path, rel: str, text: str) -> None:
    target = path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def build_repo(path: Path) -> dict[str, str]:
    """Create the repository and return `{label: sha}` for c1..c6."""
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    shas: dict[str, str] = {}

    write(path, "config/app.yaml", "app:\n  retry_limit: 3\n  name: demo\n")
    write(path, "config.toml", "[app]\nconcurrency = 10\n")
    write(path, "go.mod", "module example.com/demo\n\ngo 1.21\n\nrequire (\n\tgithub.com/lib/pq v1.10.0\n\tgithub.com/stretchr/testify v1.8.0 // indirect\n)\n")
    write(path, "cmd/main.go", "package main\n\nconst retryLimit = 3\n\ntype Server struct{}\n\nfunc (s *Server) Run() error { return nil }\n\nfunc main() {}\n")
    write(path, "README.md", "# Demo\n\nA demo repository for the ingestion tests.\n")
    write(path, "docs/adr/0001-use-postgres.md", ADR_0001)
    (path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "initial import", date=DATES[0])
    shas["c1"] = git(path, "rev-parse", "HEAD")

    write(path, "config/app.yaml", "app:\n  retry_limit: 5\n  name: demo\n")
    write(path, "config.toml", "[app]\nconcurrency = 20\n")
    git(path, "commit", "-qam", "Raise retry limit\n\nUpstream is flaky, see #12", date=DATES[1])
    shas["c2"] = git(path, "rev-parse", "HEAD")

    write(path, "go.mod", "module example.com/demo\n\ngo 1.21\n\nrequire (\n\tgithub.com/lib/pq v1.10.9\n\tgithub.com/stretchr/testify v1.8.0 // indirect\n)\n")
    write(path, "docs/adr/0001-use-postgres.md", ADR_0001_SUPERSEDED)
    write(path, "docs/adr/0002-switch-to-pgx.md", ADR_0002)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "Switch to pgx (#7)\n\nCloses #3", date=DATES[2])
    shas["c3"] = git(path, "rev-parse", "HEAD")

    git(path, "mv", "cmd/main.go", "cmd/server.go")
    git(path, "commit", "-q", "-m", "Rename main to server", date=DATES[3])
    shas["c4"] = git(path, "rev-parse", "HEAD")

    git(path, "revert", "--no-edit", shas["c2"], date=DATES[4])
    shas["c5"] = git(path, "rev-parse", "HEAD")

    write(path, "cmd/server.go", "package main\n\nconst retryLimit = 3\n\ntype Server struct{}\n\nfunc (s *Server) Run() error { return nil }\n\nfunc healthz() bool { return true }\n\nfunc main() {}\n")
    git(path, "commit", "-qam", "Fix crash on startup (#9)\n\nFixes #5", date=DATES[5])
    shas["c6"] = git(path, "rev-parse", "HEAD")
    return shas
