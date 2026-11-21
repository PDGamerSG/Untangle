"""Untangle HTTP API (CONTRACTS §6). Every endpoint is a thin wrapper over `untangle.answer.service`; the meeting and KT
endpoints delegate to `untangle.kt.service` when that package is importable and answer 501 otherwise.

Run with `uv run uvicorn untangle.api.main:app --port 8090` or `untangle serve`."""

from __future__ import annotations

import importlib
import logging
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from untangle import __version__
from untangle.answer import service
from untangle.answer.models import (
    AskRequest,
    AskResponse,
    EntityResponse,
    PulseResponse,
    RepoInfo,
    SearchResponse,
    TimelineResponse,
    WhyPath,
)
from untangle.api import meetings as meeting_shape
from untangle.api.auth import CurrentUser, charge, enforce_access
from untangle.api.auth import router as auth_router
from untangle.api.english import to_english
from untangle.api.health import shape_health
from untangle.api.repositories import router as repositories_router
from untangle.api.security import add_security_headers
from untangle.auth import limits
from untangle.config import settings
from untangle.graph.db import GraphUnavailable
from untangle.kt.sarvam import SarvamError
from untangle.repositories.models import ImportProblem
from untangle.repositories.service import normalize_repository
from untangle.repository_map.export import vault_zip
from untangle.repository_map.service import complete_repository_map, repository_map

log = logging.getLogger("untangle.api")
_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")

_docs = settings().api_docs
app = FastAPI(
    title="Untangle API", version=__version__,
    description="Answers 'why is the code like this?' from a graph of a repository's history, with evidence on every answer.",
    # Interactive documentation is for local development; production does not publish its schema.
    docs_url="/docs" if _docs else None, redoc_url=None, openapi_url="/openapi.json" if _docs else None,
    dependencies=[Depends(enforce_access)],
)
# The web app calls the API on its own origin; CORS only admits the configured development origins.
app.add_middleware(
    CORSMiddleware, allow_origins=list(settings().cors_origins) or ["http://localhost:3000"], allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"], allow_headers=["Accept", "Content-Type", "X-Request-Id"], max_age=600,
)
add_security_headers(app)
app.include_router(auth_router)
app.include_router(repositories_router)


# ------------------------------------------------------------------------------------------------------------------
# cross-cutting


@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
    supplied = request.headers.get("x-request-id", "").strip()
    # Echo a caller's id only when it is a plain token, so it cannot inject text into logs or headers.
    request_id = supplied if _REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - started) * 1000.0
    log.info("%s %s -> %d in %.0f ms", request.method, request.url.path, response.status_code, ms)
    response.headers["x-untangle-ms"] = f"{ms:.0f}"
    response.headers["x-request-id"] = request_id
    return response


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error(status: int, message: str, *, request_id: str | None = None, **extra: Any) -> JSONResponse:
    content = {"error": message, **extra}
    if request_id:
        content["request_id"] = request_id
    return JSONResponse(status_code=status, content=content)


@app.exception_handler(GraphUnavailable)
async def _graph_unavailable(request: Request, exc: GraphUnavailable) -> JSONResponse:
    return _error(503, str(exc), request_id=_request_id(request))


@app.exception_handler(service.NotFound)
async def _not_found(request: Request, exc: service.NotFound) -> JSONResponse:
    return _error(404, str(exc), request_id=_request_id(request))


@app.exception_handler(ValueError)
async def _bad_value(request: Request, exc: ValueError) -> JSONResponse:
    return _error(400, str(exc), request_id=_request_id(request))


@app.exception_handler(ImportProblem)
async def _import_problem(request: Request, exc: ImportProblem) -> JSONResponse:
    return _error(exc.status, str(exc), request_id=_request_id(request))


@app.exception_handler(SarvamError)
async def _sarvam_error(request: Request, exc: SarvamError) -> JSONResponse:
    status = 503 if exc.status in (401, 403) or "not set" in str(exc) else 502
    return _error(status, "Transcription is unavailable. Please try a transcript file or retry later.", request_id=_request_id(request))


@app.exception_handler(limits.LimitExceeded)
async def _limit_exceeded(request: Request, exc: limits.LimitExceeded) -> JSONResponse:
    response = _error(429, str(exc), request_id=_request_id(request))
    response.headers["Retry-After"] = str(exc.retry_after)
    return response


# Database and unexpected errors are logged with the request id; the response never includes internal details.
@app.exception_handler(Neo4jError)
async def _neo4j_error(request: Request, exc: Neo4jError) -> JSONResponse:
    log.error("neo4j error [%s]: %s", _request_id(request), exc)
    return _error(502, "The graph database could not complete this request. Please retry shortly.", request_id=_request_id(request))


@app.exception_handler(Exception)
async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error [%s]", _request_id(request))
    return _error(500, "Something went wrong on our side. Please retry; if it continues, share the request id.", request_id=_request_id(request))


# ------------------------------------------------------------------------------------------------------------------
# endpoints


@app.get("/health")
def health() -> dict[str, Any]:
    return shape_health(service.health())


@app.get("/repos", response_model=list[RepoInfo])
def repos() -> list[RepoInfo]:
    return service.repos()


def _english(result: Any) -> Any:
    """The response as the web app shows it: stored Hindi and Hinglish rendered in English (see `api.english`)."""
    return to_english(jsonable_encoder(result))


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request) -> Any:
    charge(request, limits.ASK, "You have asked 40 questions in the last hour. Please wait before asking more.")
    return _english(service.ask(body.question, body.repo, at=body.at, mode=body.mode))


@app.get("/decisions/{decision_id:path}", response_model=WhyPath)
def decision(decision_id: str) -> Any:
    return _english(service.why_path(decision_id[:300]))


@app.get("/entities/{entity_id:path}", response_model=EntityResponse)
def entity(entity_id: str) -> Any:
    return _english(service.entity(entity_id[:300]))


@app.get("/search", response_model=SearchResponse)
def search(repo: str = Query(min_length=3, max_length=200), q: str = Query(min_length=1, max_length=500)) -> Any:
    return _english(service.search(repo, q))


@app.get("/timeline", response_model=TimelineResponse)
def timeline(repo: str = Query(min_length=3, max_length=200), at: str | None = Query(default=None, max_length=40)) -> Any:
    return _english(service.timeline(repo, at))


@app.get("/pulse", response_model=PulseResponse)
def pulse(repo: str = Query(min_length=3, max_length=200), limit: int = Query(default=24, ge=1, le=50)) -> Any:
    return _english(service.pulse(repo, limit=limit))


@app.get("/stats")
def stats(repo: str | None = Query(default=None, min_length=3, max_length=200)) -> dict[str, Any]:
    return service.get_graph().stats(repo)


@app.get("/repository-map")
def feature_map(repo: str = Query(min_length=3, max_length=200), offset: int = Query(default=0, ge=0), limit: int = Query(default=80, ge=1, le=200), structure_page: int = Query(default=0, ge=0)) -> dict:
    return repository_map(repo, service.get_graph(), offset=offset, limit=limit, structure_page=structure_page)


@app.get("/repository-map/obsidian")
def feature_vault(repo: str = Query(min_length=3, max_length=200), offset: int = Query(default=0, ge=0), limit: int = Query(default=200, ge=1, le=200)) -> Response:
    data = complete_repository_map(repo, service.get_graph(), offset=offset, limit=limit)
    return Response(vault_zip(data), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="untangle-obsidian.zip"'})


# -- agents: the decision graph over the Model Context Protocol ------------------------------------------------------


@app.post("/mcp")
async def mcp_endpoint(request: Request, user: CurrentUser) -> Response:
    """Streamable HTTP, stateless: one JSON-RPC message per POST, answered with JSON (see `untangle.mcp_server`)."""
    import json

    from untangle import mcp_server

    try:
        message = json.loads(await request.body() or b"null")
    except ValueError:
        return JSONResponse(mcp_server._error(None, -32700, "Parse error: the body must be one JSON-RPC message."), status_code=400)

    def charge_call(kind: str) -> None:
        if user.is_admin:
            return
        graph = service.get_graph()
        limit = {"ask": limits.ASK, "write": limits.AGENT_NOTE}.get(kind)
        try:
            limits.hit(graph, limits.AGENT_CALL, user.id, "This token has made 300 tool calls in the last hour. Please wait.")
            if limit is not None:
                limits.hit(graph, limit, user.id, "This account reached its limit for this tool. Please try again later.")
        except limits.LimitExceeded as exc:
            raise mcp_server.ToolError(f"{exc} (retry in about {exc.retry_after} seconds)") from exc

    reply = await run_in_threadpool(mcp_server.handle, message, user, charge=charge_call)
    if reply is None:
        return Response(status_code=202)
    return JSONResponse(_english(reply) if "result" in reply else reply)


class AgentChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class AgentChatRequest(BaseModel):
    repo: str | None = Field(default=None, max_length=200)
    messages: list[AgentChatMessage] = Field(min_length=1, max_length=40)


@app.post("/agent/chat")
async def agent_chat(body: AgentChatRequest, request: Request, user: CurrentUser) -> Any:
    """The built-in agent on the Agents page: answers with the deployment's model and read-only graph tools."""
    from untangle import agent_chat as chat

    charge(request, limits.ASK, "You have asked 40 questions in the last hour. Please wait before asking more.")

    def charge_call(kind: str) -> None:
        if user.is_admin:
            return
        limit = limits.for_guest(limits.AGENT_CALL) if user.is_guest else limits.AGENT_CALL
        try:
            limits.hit(service.get_graph(), limit, user.id, f"The agent has made {limit.count} lookups for you in the last hour. Please wait.")
        except limits.LimitExceeded as exc:
            raise chat.AgentLimit(str(exc), exc.retry_after) from exc

    try:
        result = await run_in_threadpool(chat.chat, [m.model_dump() for m in body.messages], body.repo, user, charge=charge_call)
    except chat.AgentUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except chat.AgentLimit as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": str(exc.retry_after or 60)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _english(result)


@app.get("/agent-notes")
def agent_notes(repo: str = Query(min_length=3, max_length=200), limit: int = Query(default=20, ge=1, le=50)) -> Any:
    """Decisions that coding agents recorded through the MCP endpoint, newest first."""
    from untangle import agent_memory

    return _english({"repo": repo, "notes": agent_memory.memories(service.get_graph(), repo, limit=limit)})


@app.get("/mcp")
def mcp_stream() -> Response:
    # No server-initiated stream: this server only answers requests.
    return Response(status_code=405, headers={"Allow": "POST"})


@app.delete("/mcp")
def mcp_session_end() -> Response:
    return Response(status_code=405, headers={"Allow": "POST"})


# -- meetings / KT: owned by untangle.kt; delegated when present ----------------------------------------------------------

_KT_MISSING = "handover-call (KT) support is not installed: untangle.kt.service is missing or has no %s()"


def _kt(function: str) -> Any:
    """`untangle.kt.service.<function>` or a 501: the KT package is optional and owned by another module."""
    try:
        module = importlib.import_module("untangle.kt.service")
    except ImportError as exc:
        raise HTTPException(status_code=501, detail=_KT_MISSING % function) from exc
    fn = getattr(module, function, None)
    if fn is None:
        raise HTTPException(status_code=501, detail=_KT_MISSING % function)
    return fn


def _owner_fields(row: dict[str, Any], user: Any) -> dict[str, Any]:
    owner = row.get("uploaded_by")
    return {"uploaded_by_me": owner == user.id, "can_delete": owner == user.id or user.is_admin}


@app.get("/meetings")
def meetings(user: CurrentUser, repo: str = Query(min_length=3, max_length=200)) -> Any:
    rows = _kt("meetings")(repo, graph=service.get_graph())
    return _english([{**meeting_shape.summary_out(r), **_owner_fields(r, user)} for r in rows])


@app.get("/meetings/{meeting_id:path}")
def meeting(meeting_id: str, user: CurrentUser) -> Any:
    graph = service.get_graph()
    result = _kt("meeting")(meeting_id[:300], graph=graph)
    if result is None:
        raise HTTPException(status_code=404, detail="This handover call was not found.")
    return _english({**meeting_shape.detail_out(result, graph=graph), **_owner_fields(result.get("meeting") or result, user)})


@app.delete("/meetings/{meeting_id:path}", status_code=204)
def delete_meeting(meeting_id: str, user: CurrentUser) -> Response:
    """The uploader (or an administrator) can remove a handover call, for example when consent is withdrawn."""
    graph = service.get_graph()
    owner = graph.read("MATCH (m:Meeting {id: $id}) RETURN m.uploaded_by AS owner", {"id": meeting_id[:300]}).records
    if not owner:
        raise HTTPException(status_code=404, detail="This handover call was not found.")
    if owner[0]["owner"] != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Only the person who uploaded this handover call can delete it.")
    graph.run_named("kt_delete_meeting", {"meeting_id": meeting_id[:300]}, write=True)
    return Response(status_code=204)


_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac", ".webm", ".mp4", ".amr"}


@app.post("/kt/ingest")
async def kt_ingest(
    request: Request, user: CurrentUser,
    repo: Annotated[str, Form(min_length=3, max_length=200)], title: Annotated[str | None, Form(max_length=200)] = None,
    language: Annotated[str | None, Form(max_length=16)] = None,
    speakers: Annotated[int | None, Form(ge=1, le=12)] = None, audio: Annotated[UploadFile | None, File()] = None,
    transcript: Annotated[UploadFile | None, File()] = None,
) -> Any:
    """Multipart `{repo, title, audio | transcript}` -> `{meeting_id, utterances, decisions, ...}` from `untangle.kt.service`.
    The upload is spooled to a temporary file because the KT functions take paths (Sarvam batch jobs need one)."""
    if audio is None and transcript is None:
        raise HTTPException(status_code=400, detail="send an `audio` file or a `transcript` JSON file")
    if audio is not None and transcript is not None:
        raise HTTPException(status_code=400, detail="send exactly one audio or transcript file")
    upload = audio if audio is not None else transcript
    content = await upload.read(4_000_001)
    if len(content) > 4_000_000:
        raise HTTPException(status_code=413, detail="Uploads must be 4 MB or smaller. Use the CLI for longer recordings.")
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    function = "ingest_audio" if audio is not None else "ingest_transcript"
    ingest = _kt(function)
    # Only the extension is taken from the client's filename; the stored file name is fixed.
    suffix = Path(upload.filename or "").suffix.lower()
    if audio is not None and suffix not in _AUDIO_SUFFIXES:
        raise HTTPException(status_code=415, detail="Upload a WAV, MP3, M4A, OGG, OPUS, FLAC or WEBM recording.")
    if transcript is not None:
        if suffix not in (".json", ".txt", ""):
            raise HTTPException(status_code=415, detail="Upload the transcript as a JSON file or as text with one `Speaker: words` line per turn.")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail="The transcript must be UTF-8 text.") from exc
    graph = service.get_graph()
    repo = normalize_repository(repo)
    imported = await run_in_threadpool(graph.read, "MATCH (r:Repo {id: $id}) RETURN r.ingested_at AS at", {"id": f"repo:{repo}"})
    if not imported.records or imported.records[0]["at"] is None:
        raise HTTPException(status_code=404, detail="Import this repository from Repositories before adding handover calls to it.")
    await run_in_threadpool(charge, request, limits.HANDOVER_UPLOAD, "You can upload 10 handover calls a day. Please try again tomorrow.")

    def authorize(meeting_id: str) -> None:
        rows = graph.read("MATCH (m:Meeting {id: $id}) RETURN m.uploaded_by AS owner", {"id": meeting_id}).records
        if rows and rows[0]["owner"] != user.id and not user.is_admin:
            raise HTTPException(status_code=409, detail="A handover call with this title and date already exists and was added by someone else. Give yours a different title.")

    with tempfile.TemporaryDirectory(prefix="untangle-kt-") as tmp:
        path = Path(tmp) / f"upload{suffix or '.json'}"
        path.write_bytes(content)
        name = (title or Path(upload.filename or "handover").stem)[:200]
        if audio is not None:
            result = await run_in_threadpool(ingest, repo, name, path, language=language, num_speakers=speakers, graph=graph, before_write=authorize)
        else:
            result = await run_in_threadpool(ingest, repo, path, title=name, language=language, graph=graph, keep_audio_uri=False, before_write=authorize)
    meeting_id = result.get("meeting_id") if isinstance(result, dict) else None
    if meeting_id:
        await run_in_threadpool(graph.run_named, "kt_meeting_owner", {"meeting_id": meeting_id, "user_id": user.id}, write=True)
    return result


@app.exception_handler(ValidationError)
async def _validation(request: Request, exc: ValidationError) -> JSONResponse:
    details = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
    return _error(422, "invalid request", request_id=_request_id(request), details=details)


__all__ = ["app"]
