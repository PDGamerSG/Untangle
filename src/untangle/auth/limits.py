"""Fixed-window request limits kept in Neo4j, so every serverless instance shares one count.

A window id is `<bucket>|<subject>|<window start>`; nodes expire with their window and are pruned in batches."""

from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass

from untangle.graph.db import Graph


@dataclass(frozen=True)
class Limit:
    bucket: str
    count: int
    window_s: int


ASK = Limit("ask", 40, 3600)
HANDOVER_UPLOAD = Limit("handover", 10, 86_400)
IMPORT = Limit("import", 5, 86_400)
AGENT_CALL = Limit("agent-call", 300, 3600)
AGENT_NOTE = Limit("agent-note", 50, 86_400)
# Network-wide limits are generous because a venue, office or campus shares one address; per-account lockout and
# per-user quotas carry the real protection.
SIGN_IN_IP = Limit("signin-ip", 60, 900)
SIGN_IN_FAILURES = Limit("signin-fail", 5, 900)
SIGN_UP_IP = Limit("signup-ip", 30, 3600)


class LimitExceeded(Exception):
    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


def _window(limit: Limit, subject: str, now: float) -> tuple[str, int, int]:
    start = int(now // limit.window_s) * limit.window_s
    # Subjects can be emails or addresses: store a digest, not the value.
    digest = hashlib.sha256(subject.encode()).hexdigest()[:32]
    return f"{limit.bucket}|{digest}|{start}", (start + limit.window_s) * 1000, start + limit.window_s - int(now)


def hit(graph: Graph, limit: Limit, subject: str, message: str, *, now: float | None = None) -> int:
    """Count one event; raise `LimitExceeded` once the window's allowance is used."""
    now = time.time() if now is None else now
    key, expires_at, retry_after = _window(limit, subject, now)
    count = int(graph.run_named("rate_limit_hit", {"id": key, "expires_at": expires_at}, write=True).scalar(0))
    if random.random() < 0.02:
        prune(graph, now=now)
    if count > limit.count:
        raise LimitExceeded(message, max(1, retry_after))
    return count


def peek(graph: Graph, limit: Limit, subject: str, *, now: float | None = None) -> tuple[int, int]:
    """(events counted in the current window, seconds until it resets)."""
    now = time.time() if now is None else now
    key, _, retry_after = _window(limit, subject, now)
    return int(graph.run_named("rate_limit_peek", {"id": key}).scalar(0)), max(1, retry_after)


def prune(graph: Graph, *, now: float | None = None) -> None:
    now_ms = int((time.time() if now is None else now) * 1000)
    graph.run_named("auth_prune", {"now": now_ms}, write=True)
