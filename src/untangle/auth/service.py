"""Accounts and sessions.

A session token is 32 random bytes sent only as an HttpOnly cookie. The graph stores its SHA-256, so neither a
database read nor a log line can be replayed as a session. Resolved sessions are cached briefly per process to
avoid a database read on every request; sign-out removes the local entry immediately."""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Any

from neo4j.exceptions import ConstraintError

from untangle.auth import limits, passwords
from untangle.config import settings
from untangle.graph.db import Graph

_EMAIL = re.compile(r"[^@\s]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+\Z")
_CACHE_SECONDS = 20.0
_cache: dict[str, tuple[float, User]] = {}
_cache_lock = threading.Lock()


class AuthProblem(Exception):
    def __init__(self, status: int, message: str, *, retry_after: int | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str
    role: str
    created_at: int

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_guest(self) -> bool:
        return self.role == "guest"

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "email": "" if self.is_guest else self.email, "name": self.name, "role": self.role, "guest": self.is_guest,
                "created_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.created_at / 1000))}


# Account constraints are applied once per process before the first sign-up, so a deployment whose schema step
# was skipped still cannot hold two accounts with one email. Every statement is idempotent.
_ACCOUNT_SCHEMA = (
    "CREATE CONSTRAINT user_email IF NOT EXISTS FOR (n:User) REQUIRE n.email IS UNIQUE",
    "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (n:User) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT session_id IF NOT EXISTS FOR (n:Session) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT ratelimit_id IF NOT EXISTS FOR (n:RateLimit) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT apitoken_id IF NOT EXISTS FOR (n:ApiToken) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT user_github_id IF NOT EXISTS FOR (n:User) REQUIRE n.github_id IS UNIQUE",
    "CREATE CONSTRAINT saved_repository_id IF NOT EXISTS FOR (n:SavedRepository) REQUIRE n.id IS UNIQUE",
    "CREATE INDEX session_expires IF NOT EXISTS FOR (n:Session) ON (n.expires_at)",
    "CREATE INDEX ratelimit_expires IF NOT EXISTS FOR (n:RateLimit) ON (n.expires_at)",
)
_schema_ready = False


def ensure_account_schema(graph: Graph) -> None:
    global _schema_ready
    if _schema_ready:
        return
    try:
        graph.run_many(list(_ACCOUNT_SCHEMA))
        _schema_ready = True
    except Exception:  # noqa: BLE001 - existing duplicate data or permissions: MERGE in 80 still blocks duplicates
        logging.getLogger("untangle.auth").exception("could not apply account constraints")


def normalize_email(value: str) -> str:
    email = unicodedata.normalize("NFKC", value or "").strip().lower()
    if len(email) > 254 or not _EMAIL.fullmatch(email):
        raise AuthProblem(400, "Enter a valid email address.")
    return email


def normalize_name(value: str | None, email: str) -> str:
    name = " ".join(unicodedata.normalize("NFKC", value or "").split())
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")[:80]
    return name or email.split("@", 1)[0]


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _user(row: dict[str, Any]) -> User:
    role = "admin" if row["email"] in settings().admin_emails else (row.get("role") or "member")
    return User(id=row["id"], email=row["email"], name=row.get("name") or row["email"], role=role, created_at=int(row.get("created_at") or 0))


def _start_session(graph: Graph, user_id: str, *, rehash: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time() * 1000)
    expires = now + settings().session_days * 86_400_000
    graph.run_named("auth_create_session", {"id": token_hash(token), "user_id": user_id, "now": now, "expires_at": expires, "rehash": rehash}, write=True)
    return token


GUEST_DOMAIN = "guest.untangle.invalid"


def start_guest(graph: Graph, *, ip: str) -> tuple[User, str]:
    """A temporary account for trying Untangle. Creating an account or signing in later keeps its repositories."""
    try:
        limits.hit(graph, limits.GUEST_IP, ip, "Too many guest sessions were started from this network. Create an account to continue.")
    except limits.LimitExceeded as exc:
        raise AuthProblem(429, str(exc), retry_after=exc.retry_after) from exc
    ensure_account_schema(graph)
    key = uuid.uuid4().hex
    row = {"id": f"user:{key}", "email": f"guest-{key}@{GUEST_DOMAIN}", "name": "Guest", "role": "guest",
           "password_hash": None, "created_at": int(time.time() * 1000)}
    created = graph.run_named("auth_create_user", {"u": row}, write=True).records
    user = _user(created[0])
    return user, _start_session(graph, user.id)


def adopt_guest(graph: Graph, guest: User | None, into: User) -> None:
    """Move a guest's saved repositories and agent tokens to the account they signed in to, then delete the guest."""
    if guest is None or not guest.is_guest or guest.id == into.id:
        return
    graph.query("""MATCH (g:User {id:$guest, role:'guest'}), (u:User {id:$user})
      OPTIONAL MATCH (g)-[:SAVED]->(s:SavedRepository)
      WITH g, u, collect(s) AS saved
      FOREACH (s IN saved |
        MERGE (n:SavedRepository {id: $user + '|' + s.repo_key})
        ON CREATE SET n.user_id = $user, n.repo = s.repo, n.repo_key = s.repo_key, n.saved_at = s.saved_at,
                      n.seen_sha = s.seen_sha, n.seen_at = s.seen_at
        MERGE (u)-[:SAVED]->(n)
        DETACH DELETE s)
      WITH g
      OPTIONAL MATCH (g)-[:HAS_SESSION]->(session:Session)
      DETACH DELETE session, g""", {"guest": guest.id, "user": into.id})
    with _cache_lock:
        _cache.clear()


def _upgrade_guest(graph: Graph, guest: User, email: str, password: str, name: str | None) -> User | None:
    try:
        return _upgrade_guest_once(graph, guest, email, password, name)
    except ConstraintError:  # the same email was registered at the same moment
        return None


def _upgrade_guest_once(graph: Graph, guest: User, email: str, password: str, name: str | None) -> User | None:
    rows = graph.query("""MATCH (u:User {id:$id, role:'guest'})
      WHERE NOT EXISTS { MATCH (o:User {email:$email}) WHERE o.id <> u.id }
      SET u.email = $email, u.password_hash = $hash, u.name = $name, u.role = 'member', u.upgraded_at = $now
      RETURN u.id AS id, u.email AS email, u.name AS name, u.role AS role, u.created_at AS created_at""",
                       {"id": guest.id, "email": email, "hash": passwords.hash_password(password), "name": normalize_name(name, email),
                        "now": int(time.time() * 1000)}).records
    with _cache_lock:
        _cache.clear()
    return _user(rows[0]) if rows else None


def register(graph: Graph, email: str, password: str, name: str | None, *, ip: str, current: User | None = None) -> tuple[User, str]:
    email = normalize_email(email)
    problem = passwords.policy_problem(password or "", email)
    if problem:
        raise AuthProblem(400, problem)
    if email.endswith("@" + GUEST_DOMAIN):
        raise AuthProblem(400, "Enter a valid email address.")
    if current is not None and current.is_guest:
        upgraded = _upgrade_guest(graph, current, email, password, name)
        if upgraded is None:
            raise AuthProblem(409, "An account with this email already exists. Sign in instead.")
        return upgraded, _start_session(graph, upgraded.id)
    try:
        limits.hit(graph, limits.SIGN_UP_IP, ip, "Too many accounts were created from this network. Try again later.")
    except limits.LimitExceeded as exc:
        raise AuthProblem(429, str(exc), retry_after=exc.retry_after) from exc
    row = {"id": f"user:{uuid.uuid4().hex}", "email": email, "name": normalize_name(name, email), "role": "member",
           "password_hash": passwords.hash_password(password), "created_at": int(time.time() * 1000)}
    ensure_account_schema(graph)
    try:
        created = graph.run_named("auth_create_user", {"u": row}, write=True).records
    except ConstraintError as exc:
        raise AuthProblem(409, "An account with this email already exists. Sign in instead.") from exc
    if not created or not created[0]["created"]:
        raise AuthProblem(409, "An account with this email already exists. Sign in instead.")
    user = _user(created[0])
    return user, _start_session(graph, user.id)


def sign_in(graph: Graph, email: str, password: str, *, ip: str) -> tuple[User, str]:
    try:
        email = normalize_email(email)
    except AuthProblem:
        raise AuthProblem(401, "Email or password is incorrect.") from None
    try:
        limits.hit(graph, limits.SIGN_IN_IP, ip, "Too many sign-in attempts from this network. Try again in a few minutes.")
    except limits.LimitExceeded as exc:
        raise AuthProblem(429, str(exc), retry_after=exc.retry_after) from exc
    failures, retry_after = limits.peek(graph, limits.SIGN_IN_FAILURES, email)
    if failures >= limits.SIGN_IN_FAILURES.count:
        raise AuthProblem(429, "Too many incorrect passwords for this account. Try again in a few minutes.", retry_after=retry_after)
    rows = graph.run_named("auth_user_by_email", {"email": email}).records
    stored = rows[0]["password_hash"] if rows else None
    if not passwords.verify(stored, (password or "")[: passwords.MAX_LENGTH]):
        try:
            limits.hit(graph, limits.SIGN_IN_FAILURES, email, "")
        except limits.LimitExceeded:
            pass
        raise AuthProblem(401, "Email or password is incorrect.")
    user = _user(rows[0])
    rehash = passwords.hash_password(password) if passwords.needs_rehash(stored) else None
    return user, _start_session(graph, user.id, rehash=rehash)


def resolve(graph: Graph, token: str | None) -> User | None:
    if not token or len(token) > 200:
        return None
    key = token_hash(token)
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    rows = graph.run_named("auth_session_user", {"id": key, "now": int(now * 1000)}).records
    if not rows:
        with _cache_lock:
            _cache.pop(key, None)
        return None
    user = _user(rows[0])
    with _cache_lock:
        if len(_cache) > 5000:
            _cache.clear()
        # Never cache past the session's own expiry.
        _cache[key] = (min(now + _CACHE_SECONDS, rows[0]["expires_at"] / 1000), user)
    return user


def sign_out(graph: Graph, token: str | None) -> None:
    if not token or len(token) > 200:
        return
    key = token_hash(token)
    with _cache_lock:
        _cache.pop(key, None)
    graph.run_named("auth_revoke_session", {"id": key}, write=True)


def delete_account(graph: Graph, user: User) -> None:
    with _cache_lock:
        _cache.clear()
    graph.run_named("auth_delete_user", {"user_id": user.id}, write=True)


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
