"""Sign in with GitHub.

Each public origin has its own GitHub OAuth App, because an OAuth App accepts one callback host. Configure them as
`GITHUB_OAUTH_APPS`, a JSON object from origin to credentials:
`{"https://untangle.pallabdas.me": {"client_id": "...", "client_secret": "..."}}`.

The app asks only for `read:user user:email`: enough to identify the person and read their verified email. It never
asks for repository access, so the hosted deployment still imports public repositories only. The GitHub access
token is used once during the callback and never stored.

Accounts link in this order: an account already linked to the GitHub user id; the signed-in account (connecting
GitHub from settings); an account whose email matches the person's verified primary GitHub email; otherwise a new
account without a password."""

from __future__ import annotations

import json
import secrets
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from untangle.auth import limits
from untangle.auth.service import AuthProblem, User, _start_session, _user, ensure_account_schema, normalize_name
from untangle.config import settings
from untangle.graph.db import Graph

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_URL = "https://api.github.com"
SCOPE = "read:user user:email"
CALLBACK_PATH = "/api/auth/github/callback"
_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "Untangle-sign-in", "X-GitHub-Api-Version": "2022-11-28"}


@dataclass(frozen=True)
class OAuthApp:
    client_id: str
    client_secret: str


def apps() -> dict[str, OAuthApp]:
    raw = settings().github_oauth_apps
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    result = {}
    for origin, value in (data.items() if isinstance(data, dict) else []):
        if isinstance(value, dict) and value.get("client_id") and value.get("client_secret"):
            result[origin.rstrip("/").lower()] = OAuthApp(str(value["client_id"]), str(value["client_secret"]))
    return result


def app_for(origin: str | None) -> OAuthApp | None:
    return apps().get((origin or "").rstrip("/").lower()) if origin else None


def safe_next(value: str | None) -> str:
    """Only same-site relative paths, so the callback cannot be turned into an open redirect."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value or len(value) > 300:
        return "/repositories"
    return value


def new_state() -> str:
    return secrets.token_urlsafe(24)


def authorize_url(app: OAuthApp, origin: str, state: str) -> str:
    query = {"client_id": app.client_id, "redirect_uri": origin.rstrip("/") + CALLBACK_PATH, "scope": SCOPE,
             "state": state, "allow_signup": "true"}
    return f"{AUTHORIZE_URL}?{urlencode(query)}"


def exchange_code(app: OAuthApp, origin: str, code: str, *, client: httpx.Client | None = None) -> str:
    body = {"client_id": app.client_id, "client_secret": app.client_secret, "code": code,
            "redirect_uri": origin.rstrip("/") + CALLBACK_PATH}
    try:
        with client or httpx.Client(timeout=15) as http:
            response = http.post(TOKEN_URL, data=body, headers={"Accept": "application/json", "User-Agent": "Untangle-sign-in"})
        token = response.json().get("access_token") if response.status_code == 200 else None
    except (httpx.HTTPError, ValueError) as exc:
        raise AuthProblem(503, "GitHub could not be reached. Try again shortly.") from exc
    if not token:
        raise AuthProblem(400, "GitHub sign-in expired or was cancelled. Try again.")
    return token


def fetch_profile(token: str, *, client: httpx.Client | None = None) -> dict:
    headers = {**_HEADERS, "Authorization": f"Bearer {token}"}
    try:
        with client or httpx.Client(timeout=15) as http:
            user = http.get(f"{API_URL}/user", headers=headers)
            emails = http.get(f"{API_URL}/user/emails", headers=headers)
    except httpx.HTTPError as exc:
        raise AuthProblem(503, "GitHub could not be reached. Try again shortly.") from exc
    if user.status_code != 200:
        raise AuthProblem(400, "GitHub did not return your profile. Try again.")
    data = user.json()
    email = None
    if emails.status_code == 200:
        rows = [e for e in emails.json() if isinstance(e, dict) and e.get("verified")]
        primary = next((e for e in rows if e.get("primary")), rows[0] if rows else None)
        email = primary.get("email") if primary else None
    return {"id": int(data["id"]), "login": str(data["login"]), "name": data.get("name") or "",
            "avatar_url": data.get("avatar_url") or "", "email": (email or "").strip().lower() or None}


_LINK = """MATCH (u:User {id: $user_id})
SET u.github_id = $p.id, u.github_login = $p.login, u.avatar_url = $p.avatar_url,
    u.github_linked_at = coalesce(u.github_linked_at, $now)
RETURN u.id AS id, u.email AS email, u.name AS name, u.role AS role, u.created_at AS created_at"""


def _linked(graph: Graph, github_id: int) -> dict | None:
    rows = graph.read("""MATCH (u:User {github_id: $id})
      RETURN u.id AS id, u.email AS email, u.name AS name, u.role AS role, u.created_at AS created_at LIMIT 1""",
                      {"id": github_id}).records
    return rows[0] if rows else None


def sign_in(graph: Graph, profile: dict, *, current: User | None, ip: str) -> tuple[User, str]:
    """Return the account for this GitHub identity and a new session token."""
    ensure_account_schema(graph)
    try:
        limits.hit(graph, limits.SIGN_IN_IP, ip, "Too many sign-in attempts from this network. Try again in a few minutes.")
    except limits.LimitExceeded as exc:
        raise AuthProblem(429, str(exc), retry_after=exc.retry_after) from exc
    now = int(time.time() * 1000)
    existing = _linked(graph, profile["id"])
    if existing:
        if current and current.id != existing["id"]:
            raise AuthProblem(409, "That GitHub account is already connected to another Untangle account.")
        row = graph.query(_LINK, {"user_id": existing["id"], "p": profile, "now": now}).records[0]
        return _user(row), _start_session(graph, row["id"])
    if current:
        row = graph.query("MATCH (u:User {id:$id}) RETURN u.github_id AS gid", {"id": current.id}).records
        if row and row[0]["gid"] is not None:
            raise AuthProblem(409, "This Untangle account is already connected to a different GitHub account.")
        row = graph.query(_LINK, {"user_id": current.id, "p": profile, "now": now}).records[0]
        return _user(row), _start_session(graph, row["id"])
    if profile["email"]:
        rows = graph.read("MATCH (u:User {email:$email}) RETURN u.id AS id, u.github_id AS gid", {"email": profile["email"]}).records
        if rows and rows[0]["gid"] is None:
            row = graph.query(_LINK, {"user_id": rows[0]["id"], "p": profile, "now": now}).records[0]
            return _user(row), _start_session(graph, row["id"])
    try:
        limits.hit(graph, limits.SIGN_UP_IP, ip, "Too many accounts were created from this network. Try again later.")
    except limits.LimitExceeded as exc:
        raise AuthProblem(429, str(exc), retry_after=exc.retry_after) from exc
    email = profile["email"] or f"{profile['id']}+{profile['login'].lower()}@users.noreply.github.com"
    row = {"id": f"user:{uuid.uuid4().hex}", "email": email, "name": normalize_name(profile["name"] or profile["login"], email),
           "role": "member", "password_hash": None, "created_at": now}
    created = graph.run_named("auth_create_user", {"u": row}, write=True).records
    if not created or not created[0]["created"]:
        raise AuthProblem(409, "An account with your GitHub email already exists. Sign in with your password, then connect GitHub.")
    linked = graph.query(_LINK, {"user_id": created[0]["id"], "p": profile, "now": now}).records[0]
    return _user(linked), _start_session(graph, linked["id"])


def identity(graph: Graph, user: User) -> dict | None:
    rows = graph.read("MATCH (u:User {id:$id}) RETURN u.github_login AS login, u.avatar_url AS avatar_url, u.github_id AS id",
                      {"id": user.id}).records
    if not rows or rows[0]["id"] is None:
        return None
    return {"login": rows[0]["login"], "avatar_url": rows[0]["avatar_url"]}


def disconnect(graph: Graph, user: User) -> bool:
    """Remove the GitHub link. Refused for an account without a password, which would then be unreachable."""
    rows = graph.read("MATCH (u:User {id:$id}) RETURN u.password_hash IS NOT NULL AS has_password", {"id": user.id}).records
    if not rows or not rows[0]["has_password"]:
        return False
    graph.query("MATCH (u:User {id:$id}) REMOVE u.github_id, u.github_login, u.avatar_url, u.github_linked_at", {"id": user.id})
    return True
