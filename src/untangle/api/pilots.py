"""Pilot and plan requests from the public pricing page.

Anyone may send one, signed in or not. Requests are limited per network address and stored as `PilotRequest`
nodes for the sales follow-up; the network address itself is kept only as a digest. Addresses at reserved example
domains (RFC 2606 and RFC 6761) are checked like any other request but never stored, so live checks leave no
records behind. Administrators read the requests with `GET /pilot-requests`."""

from __future__ import annotations

import hashlib
import re
import secrets
import time
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from untangle.answer import service as answers
from untangle.api.auth import client_ip, session_token
from untangle.auth import limits
from untangle.auth import service as accounts

router = APIRouter(prefix="/pilot-requests")

# A shared office or campus network may send a few; more than this in an hour is almost certainly automated.
PILOT_IP = limits.Limit("pilot-ip", 8, 3600)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RESERVED_DOMAINS = ("example.com", "example.net", "example.org")
_RESERVED_SUFFIXES = (".test", ".example", ".invalid", ".localhost")
# Unambiguous characters only, so a reference read out on a call is not misheard.
_REFERENCE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


class PilotRequestBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    company: str = Field(min_length=1, max_length=160)
    role: str | None = Field(default=None, max_length=120)
    team_size: int = Field(ge=1, le=1_000_000)
    plan: Literal["transition", "team", "enterprise"]
    message: str | None = Field(default=None, max_length=2000)
    # Hidden from people on the form; automated submitters fill it in.
    website: str | None = Field(default=None, max_length=200)


def reference() -> str:
    return "UT-" + "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(6))


def reserved(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].lower()
    return domain in _RESERVED_DOMAINS or any(domain.endswith(s) or domain == s[1:] for s in _RESERVED_SUFFIXES) \
        or any(domain.endswith(f".{d}") for d in _RESERVED_DOMAINS)


def _text(value: str | None) -> str | None:
    cleaned = " ".join((value or "").split())
    return cleaned or None


def _required(value: str, field: str) -> str:
    cleaned = _text(value)
    if cleaned is None:
        raise HTTPException(status_code=400, detail=f"Enter your {field}.")
    return cleaned


@router.post("", status_code=201)
async def create_pilot_request(body: PilotRequestBody, request: Request) -> dict:
    """Store a request and return the reference the follow-up will quote."""
    name = _required(body.name, "name")
    company = _required(body.company, "company")
    email = body.email.strip().lower()
    if not _EMAIL.fullmatch(email):
        raise HTTPException(status_code=400, detail="Enter a work email address, such as you@company.com.")
    message = (body.message or "").strip() or None
    ref = reference()
    accepted = {"reference": ref, "plan": body.plan, "follow_up": "within one working day"}
    if _text(body.website):
        # Answer as if accepted so an automated submitter learns nothing, and store nothing.
        return {**accepted, "stored": False}

    graph = answers.get_graph()
    ip = client_ip(request)
    try:
        await run_in_threadpool(limits.hit, graph, PILOT_IP, ip,
                                "Too many requests from this network in the last hour. Please try again later.")
    except limits.LimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": str(exc.retry_after)}) from exc
    if reserved(email):
        return {**accepted, "stored": False}

    user = await run_in_threadpool(accounts.resolve, graph, session_token(request))
    record = {
        "id": f"pilot_{uuid.uuid4().hex[:16]}", "reference": ref, "name": name, "email": email, "company": company,
        "role": _text(body.role), "team_size": body.team_size, "plan": body.plan, "message": message,
        "user_id": user.id if user is not None else None, "status": "new",
        "ip_digest": hashlib.sha256(ip.encode()).hexdigest()[:32], "created_at": int(time.time() * 1000),
    }
    await run_in_threadpool(graph.run_named, "pilot_request_create", {"p": record}, write=True)
    return {**accepted, "stored": True}


@router.get("")
def list_pilot_requests(request: Request, limit: int = Query(default=100, ge=1, le=500)) -> dict:
    """Newest first, for administrators. The route is public so the form can post without a session, so this
    handler checks the session itself."""
    user = accounts.resolve(answers.get_graph(), session_token(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to use Untangle.")
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can read pilot requests.")
    rows = answers.get_graph().run_named("pilot_requests_list", {"limit": limit}).records
    for row in rows:
        created = row.pop("created_at", None)
        row["created_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created / 1000)) if created else None
    return {"requests": rows}
