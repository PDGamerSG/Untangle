"""Sign-up, sign-in and the access rule every API route passes through.

Only `/health`, the sign-in endpoints and the pricing page's pilot request form are public. Every other route needs a valid session cookie; the
resolved user is available as `request.state.user`. State-changing requests from browsers must come from a
trusted origin (the session cookie is also SameSite=Lax), which blocks cross-site request forgery."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from untangle.answer import service as answers
from untangle.auth import github, limits, tokens
from untangle.auth import service as accounts
from untangle.auth.service import AuthProblem, User
from untangle.config import settings

PUBLIC_ROUTES = frozenset({"/health", "/auth/register", "/auth/login", "/auth/logout", "/auth/me", "/auth/guest", "/auth/github/start",
                           "/auth/github/callback", "/auth/providers", "/pilot-requests"})
# Routes a coding agent may call with a personal access token instead of a browser session.
TOKEN_ROUTES = frozenset({"/mcp"})
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

router = APIRouter(prefix="/auth")


def cookie_name() -> str:
    # The __Host- prefix makes browsers refuse the cookie unless it is Secure, host-only and scoped to "/".
    return "__Host-untangle_session" if settings().cookie_secure else "untangle_session"


def session_token(request: Request) -> str | None:
    return request.cookies.get(cookie_name())


def client_ip(request: Request) -> str:
    # Vercel overwrites these headers at its edge; a client cannot choose them.
    for header in ("x-vercel-forwarded-for", "x-real-ip", "x-forwarded-for"):
        value = request.headers.get(header, "").split(",")[0].strip()
        if value:
            return value[:64]
    return request.client.host if request.client else "unknown"


def _own_origins(request: Request) -> set[str]:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    hosts = {request.headers.get("x-forwarded-host", "").split(",")[0].strip(), request.headers.get("host", "").strip()}
    return {f"{proto}://{h}" for h in hosts if h}


def origin_allowed(request: Request) -> bool:
    """Browsers send Origin (or Sec-Fetch-Site) on state-changing requests; non-browser clients send neither."""
    origin = request.headers.get("origin")
    if origin:
        parts = urlsplit(origin)
        normalized = f"{parts.scheme}://{parts.netloc}".lower()
        return normalized in {o.lower() for o in settings().trusted_origins} | {o.lower() for o in _own_origins(request)}
    site = request.headers.get("sec-fetch-site")
    return site in (None, "same-origin", "none")


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(cookie_name(), token, max_age=settings().session_days * 86_400, path="/", httponly=True,
                        secure=settings().cookie_secure, samesite="lax")


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(cookie_name(), path="/", httponly=True, secure=settings().cookie_secure, samesite="lax")


def _problem(exc: AuthProblem) -> HTTPException:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    return HTTPException(status_code=exc.status, detail=str(exc), headers=headers)


def enforce_access(request: Request) -> None:
    """Application-wide dependency: reject cross-site writes, then require a session outside PUBLIC_ROUTES."""
    if request.method in UNSAFE_METHODS and not origin_allowed(request):
        raise HTTPException(status_code=403, detail="This request came from a site Untangle does not trust.")
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    if path in PUBLIC_ROUTES:
        return
    if path in TOKEN_ROUTES:
        bearer = request.headers.get("authorization", "")
        token = bearer[7:].strip() if bearer[:7].lower() == "bearer " else None
        user = tokens.resolve(answers.get_graph(), token) if token else accounts.resolve(answers.get_graph(), session_token(request))
        if user is None:
            raise HTTPException(status_code=401, detail="Send a personal access token: Authorization: Bearer utg_…",
                                headers={"WWW-Authenticate": 'Bearer realm="untangle"'})
        request.state.user = user
        return
    user = accounts.resolve(answers.get_graph(), session_token(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to use Untangle.")
    request.state.user = user


def current_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to use Untangle.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def charge(request: Request, limit: limits.Limit, message: str) -> None:
    """Count one use of a limited action for the signed-in user. Administrators are not limited."""
    user = current_user(request)
    if user.is_admin:
        return
    if user.is_guest:
        limit = limits.for_guest(limit)
        message = f"{message} Guests have a smaller allowance: create an account for more."
    elif user.plan in limits.PAID_PLANS:
        limit = limits.for_plan(limit, user.plan)
        names = {"team": "Team", "transition": "Transition Pack", "enterprise": "Enterprise"}
        message = f"This account reached the {names[user.plan]} plan limit of {limit.count} for this period. Please wait."
    else:
        message = f"{message} Paid plans raise this limit: see /pricing."
    try:
        limits.hit(answers.get_graph(), limit, user.id, message)
    except limits.LimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": str(exc.retry_after)}) from exc


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=512)
    name: str | None = Field(default=None, max_length=200)


class SignInRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=512)


@router.post("/guest", status_code=201)
async def guest(request: Request, response: Response) -> dict:
    """Try Untangle without an account. An existing session is kept rather than replaced."""
    current = accounts.resolve(answers.get_graph(), session_token(request))
    if current is not None:
        return {"user": current.public()}
    try:
        user, token = await run_in_threadpool(accounts.start_guest, answers.get_graph(), ip=client_ip(request))
    except AuthProblem as exc:
        raise _problem(exc) from exc
    _set_cookie(response, token)
    return {"user": user.public()}


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, request: Request, response: Response) -> dict:
    current = accounts.resolve(answers.get_graph(), session_token(request))
    try:
        user, token = await run_in_threadpool(accounts.register, answers.get_graph(), body.email, body.password, body.name,
                                              ip=client_ip(request), current=current)
    except AuthProblem as exc:
        raise _problem(exc) from exc
    _set_cookie(response, token)
    return {"user": user.public()}


@router.post("/login")
async def login(body: SignInRequest, request: Request, response: Response) -> dict:
    current = accounts.resolve(answers.get_graph(), session_token(request))
    try:
        user, token = await run_in_threadpool(accounts.sign_in, answers.get_graph(), body.email, body.password, ip=client_ip(request))
    except AuthProblem as exc:
        raise _problem(exc) from exc
    await run_in_threadpool(accounts.adopt_guest, answers.get_graph(), current, user)
    _set_cookie(response, token)
    return {"user": user.public()}


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response) -> Response:
    token = session_token(request)
    if token:
        await run_in_threadpool(accounts.sign_out, answers.get_graph(), token)
    result = Response(status_code=204)
    _clear_cookie(result)
    return result


@router.get("/me")
def me(request: Request) -> dict:
    """The signed-in account, or `{"user": null}`: being signed out is an answer here, not an error, so the sign-in
    page does not log a failed request in the browser console."""
    user = accounts.resolve(answers.get_graph(), session_token(request))
    return {"user": user.public() if user is not None else None}


def _allowance(user: User, limit: limits.Limit) -> dict | None:
    """How much of the current window's allowance this person has used; None for administrators, who are not
    limited."""
    if user.is_admin:
        return None
    applied = limits.for_guest(limit) if user.is_guest else limits.for_plan(limit, user.plan)
    used, resets_in = limits.peek(answers.get_graph(), applied, user.id)
    return {"used": min(used, applied.count), "limit": applied.count, "window_s": applied.window_s, "resets_in_s": resets_in}


@router.get("/usage")
def usage(user: CurrentUser) -> dict:
    """The account's plan and how much of this hour's questions and today's handover calls it has used."""
    plan = "guest" if user.is_guest else user.plan
    return {"plan": plan, "unlimited": user.is_admin, "questions": _allowance(user, limits.ASK),
            "handover_calls": _allowance(user, limits.HANDOVER_UPLOAD)}


@router.delete("/account", status_code=204)
def delete_account(user: CurrentUser) -> Response:
    accounts.delete_account(answers.get_graph(), user)
    result = Response(status_code=204)
    _clear_cookie(result)
    return result


class TokenRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)


@router.get("/tokens")
def list_tokens(user: CurrentUser) -> dict:
    return {"tokens": tokens.list_tokens(answers.get_graph(), user), "max": tokens.MAX_TOKENS}


@router.post("/tokens", status_code=201)
def create_token(body: TokenRequest, user: CurrentUser) -> dict:
    """The token is in this response only; Untangle keeps just its hash."""
    if user.is_guest:
        raise HTTPException(status_code=403, detail="Create an account to connect your own agent.")
    try:
        return tokens.create(answers.get_graph(), user, body.name)
    except AuthProblem as exc:
        raise _problem(exc) from exc


@router.delete("/tokens/{token_id}", status_code=204)
def revoke_token(token_id: str, user: CurrentUser) -> Response:
    if not tokens.revoke(answers.get_graph(), user, token_id[:32]):
        raise HTTPException(status_code=404, detail="That token was not found.")
    return Response(status_code=204)


# ---- Sign in with GitHub ------------------------------------------------------------------------------------------


def _state_cookie() -> str:
    return "__Host-untangle_github" if settings().cookie_secure else "untangle_github"


def public_origin(request: Request) -> str | None:
    """This request's own origin, only when it is a trusted public origin (never a client-chosen Host)."""
    trusted = {o.lower() for o in settings().trusted_origins}
    return next((o for o in sorted(_own_origins(request)) if o.lower() in trusted), None)


@router.get("/providers")
def providers(request: Request) -> dict:
    return {"github": github.app_for(public_origin(request)) is not None}


@router.get("/github/start")
def github_start(request: Request, next: str | None = Query(default=None, max_length=300)) -> Response:
    origin = public_origin(request)
    app = github.app_for(origin)
    if app is None or origin is None:
        return RedirectResponse("/login?error=github-unavailable", status_code=303)
    state = github.new_state()
    response = RedirectResponse(github.authorize_url(app, origin, state), status_code=303)
    response.set_cookie(_state_cookie(), f"{state}|{github.safe_next(next)}", max_age=600, path="/", httponly=True,
                        secure=settings().cookie_secure, samesite="lax")
    return response


@router.get("/github/callback")
async def github_callback(request: Request, code: str | None = Query(default=None, max_length=200),
                          state: str | None = Query(default=None, max_length=200),
                          error: str | None = Query(default=None, max_length=200)) -> Response:
    import hmac
    stored, _, next_path = (request.cookies.get(_state_cookie()) or "").partition("|")
    origin = public_origin(request)
    app = github.app_for(origin)

    def fail(reason: str) -> Response:
        result = RedirectResponse(f"/login?error={reason}", status_code=303)
        result.delete_cookie(_state_cookie(), path="/", httponly=True, secure=settings().cookie_secure, samesite="lax")
        return result

    if error:
        return fail("github-cancelled")
    if not code or not state or not stored or not hmac.compare_digest(stored, state) or app is None or origin is None:
        return fail("github-expired")
    current = accounts.resolve(answers.get_graph(), session_token(request))
    try:
        access = await run_in_threadpool(github.exchange_code, app, origin, code)
        profile = await run_in_threadpool(github.fetch_profile, access)
        _user_row, token = await run_in_threadpool(github.sign_in, answers.get_graph(), profile, current=current, ip=client_ip(request))
    except AuthProblem as exc:
        return fail("github-conflict" if exc.status == 409 else "github-limited" if exc.status == 429 else "github-failed")
    result = RedirectResponse(github.safe_next(next_path), status_code=303)
    result.delete_cookie(_state_cookie(), path="/", httponly=True, secure=settings().cookie_secure, samesite="lax")
    _set_cookie(result, token)
    return result


@router.get("/github")
def github_identity(user: CurrentUser) -> dict:
    return {"github": github.identity(answers.get_graph(), user)}


@router.delete("/github", status_code=204)
def github_disconnect(user: CurrentUser) -> Response:
    if not github.disconnect(answers.get_graph(), user):
        raise HTTPException(status_code=409, detail="Set a password before disconnecting GitHub, or you could not sign in again.")
    return Response(status_code=204)
