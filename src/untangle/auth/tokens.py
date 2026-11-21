"""Personal access tokens that let a user's coding agents use Untangle's graph tools over MCP.

A token is shown once (`utg_` followed by 43 URL-safe characters). The graph keeps only its SHA-256, so a database
read cannot be turned back into a working token. Tokens act as the user who created them, only on the agent
endpoint, and are revoked by deleting them."""

from __future__ import annotations

import secrets
import threading
import time
import unicodedata
from typing import Any

from untangle.auth.service import AuthProblem, User, _user, token_hash
from untangle.graph.db import Graph

PREFIX = "utg_"
MAX_TOKENS = 10
_CACHE_SECONDS = 20.0
_cache: dict[str, tuple[float, User]] = {}
_lock = threading.Lock()


def _iso(ms: int | None) -> str | None:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ms / 1000)) if ms else None


def create(graph: Graph, user: User, name: str | None) -> dict[str, Any]:
    label = " ".join(unicodedata.normalize("NFKC", name or "").split())[:60] or "Coding agent"
    token = PREFIX + secrets.token_urlsafe(32)
    now = int(time.time() * 1000)
    row = {"id": token_hash(token), "user_id": user.id, "name": label, "prefix": token[:8], "created_at": now}
    created = graph.run_named("api_token_create", {"t": row, "max": MAX_TOKENS}, write=True).records
    if not created:
        raise AuthProblem(409, f"You already have {MAX_TOKENS} agent tokens. Revoke one before creating another.")
    return {"id": row["id"][:16], "name": label, "prefix": row["prefix"], "created_at_iso": _iso(now), "token": token}


def list_tokens(graph: Graph, user: User) -> list[dict[str, Any]]:
    rows = graph.run_named("api_tokens_list", {"user_id": user.id}).records
    return [{"id": r["id"][:16], "name": r["name"], "prefix": r["prefix"], "created_at_iso": _iso(r["created_at"]),
             "last_used_at_iso": _iso(r.get("last_used_at"))} for r in rows]


def revoke(graph: Graph, user: User, short_id: str) -> bool:
    """Revoke by the 16-character id shown in the list; only the owner's own tokens can match."""
    if not short_id or len(short_id) != 16 or not all(c in "0123456789abcdef" for c in short_id):
        return False
    rows = graph.run_named("api_tokens_list", {"user_id": user.id}).records
    match = next((r["id"] for r in rows if r["id"].startswith(short_id)), None)
    if match is None:
        return False
    graph.run_named("api_token_revoke", {"user_id": user.id, "id": match}, write=True)
    with _lock:
        _cache.pop(match, None)
    return True


def resolve(graph: Graph, token: str | None) -> User | None:
    if not token or not token.startswith(PREFIX) or len(token) > 100:
        return None
    key = token_hash(token)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    rows = graph.run_named("api_token_user", {"id": key}).records
    if not rows:
        return None
    user = _user(rows[0])
    graph.run_named("api_token_used", {"id": key, "now": int(now * 1000)}, write=True)
    with _lock:
        if len(_cache) > 5000:
            _cache.clear()
        _cache[key] = (now + _CACHE_SECONDS, user)
    return user


def clear_cache() -> None:
    with _lock:
        _cache.clear()
