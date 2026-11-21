"""Sign-up, sign-in and the access rule every API route passes through.

Only `/health` and the sign-in endpoints are public. Every other route needs a valid session cookie; the
resolved user is available as `request.state.user`. State-changing requests from browsers must come from a
trusted origin (the session cookie is also SameSite=Lax), which blocks cross-site request forgery."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from untangle.answer import service as answers
from untangle.auth import limits
from untangle.auth import service as accounts
from untangle.auth.service import AuthProblem, User
from untangle.config import settings

PUBLIC_ROUTES = frozenset({"/health", "/auth/register", "/auth/login", "/auth/logout", "/auth/me"})
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


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, request: Request, response: Response) -> dict:
    try:
        user, token = await run_in_threadpool(accounts.register, answers.get_graph(), body.email, body.password, body.name, ip=client_ip(request))
    except AuthProblem as exc:
        raise _problem(exc) from exc
    _set_cookie(response, token)
    return {"user": user.public()}


@router.post("/login")
async def login(body: SignInRequest, request: Request, response: Response) -> dict:
    try:
        user, token = await run_in_threadpool(accounts.sign_in, answers.get_graph(), body.email, body.password, ip=client_ip(request))
    except AuthProblem as exc:
        raise _problem(exc) from exc
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
    user = accounts.resolve(answers.get_graph(), session_token(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to use Untangle.")
    return {"user": user.public()}


@router.delete("/account", status_code=204)
def delete_account(user: CurrentUser) -> Response:
    accounts.delete_account(answers.get_graph(), user)
    result = Response(status_code=204)
    _clear_cookie(result)
    return result
