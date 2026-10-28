"""Untangle HTTP API (CONTRACTS §6). Every endpoint is a thin wrapper over `untangle.answer.service`; the meeting and KT
endpoints delegate to `untangle.kt.service` when that package is importable and answer 501 otherwise.

Run with `uv run uvicorn untangle.api.main:app --port 8090` or `untangle serve`."""

from __future__ import annotations

import importlib
import logging
import tempfile
import time
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from neo4j.exceptions import Neo4jError
from pydantic import ValidationError

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
from untangle.api.health import shape_health
from untangle.config import settings
from untangle.graph.db import GraphUnavailable

log = logging.getLogger("untangle.api")

app = FastAPI(
    title="Untangle API", version=__version__,
    description="Answers 'why is the code like this?' from a graph of a repository's history, with evidence on every answer.",
)
app.add_middleware(
    CORSMiddleware, allow_origins=list(settings().cors_origins) or ["http://localhost:3000"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ------------------------------------------------------------------------------------------------------------------
# cross-cutting


@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id", "").strip()[:128] or uuid.uuid4().hex
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


@app.exception_handler(Neo4jError)
async def _neo4j_error(request: Request, exc: Neo4jError) -> JSONResponse:
    log.error("neo4j error: %s", exc)
    return _error(502, f"graph query failed: {exc.message if hasattr(exc, 'message') else exc}", request_id=_request_id(request), code=getattr(exc, "code", None))


@app.exception_handler(Exception)
async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error")
    return _error(500, f"{type(exc).__name__}: {exc}", request_id=_request_id(request))


# ------------------------------------------------------------------------------------------------------------------
# endpoints


@app.get("/health")
def health() -> dict[str, Any]:
    return shape_health(service.health())


@app.get("/repos", response_model=list[RepoInfo])
def repos() -> list[RepoInfo]:
    return service.repos()


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest) -> AskResponse:
    return service.ask(body.question, body.repo, at=body.at, mode=body.mode)


@app.get("/decisions/{decision_id:path}", response_model=WhyPath)
def decision(decision_id: str) -> WhyPath:
    return service.why_path(decision_id)


@app.get("/entities/{entity_id:path}", response_model=EntityResponse)
def entity(entity_id: str) -> EntityResponse:
    return service.entity(entity_id)


@app.get("/search", response_model=SearchResponse)
def search(repo: str = Query(min_length=3), q: str = Query(min_length=1, max_length=500)) -> SearchResponse:
    return service.search(repo, q)


@app.get("/timeline", response_model=TimelineResponse)
def timeline(repo: str = Query(min_length=3), at: str | None = None) -> TimelineResponse:
    return service.timeline(repo, at)


@app.get("/pulse", response_model=PulseResponse)
def pulse(repo: str = Query(min_length=3), limit: int = Query(default=24, ge=1, le=50)) -> PulseResponse:
    return service.pulse(repo, limit=limit)


@app.get("/stats")
def stats(repo: str | None = None) -> dict[str, Any]:
    return service.get_graph().stats(repo)


# -- meetings / KT: owned by untangle.kt; delegated when present ----------------------------------------------------------

_KT_MISSING = "handover-call (KT) support is not installed: untangle.kt.service is missing or has no %s()"


def _kt(function: str) -> Any:
    """`untangle.kt.service.<function>` or a 501: the KT package is optional and owned by another module."""
    try:
        module = importlib.import_module("untangle.kt.service")
    except ImportError as exc:
        raise HTTPException(status_code=501, detail=f"{_KT_MISSING % function} ({exc})") from exc
    fn = getattr(module, function, None)
    if fn is None:
        raise HTTPException(status_code=501, detail=_KT_MISSING % function)
    return fn


@app.get("/meetings")
def meetings(repo: str = Query(min_length=3)) -> Any:
    return [meeting_shape.summary_out(r) for r in _kt("meetings")(repo, graph=service.get_graph())]


@app.get("/meetings/{meeting_id:path}")
def meeting(meeting_id: str) -> Any:
    graph = service.get_graph()
    result = _kt("meeting")(meeting_id, graph=graph)
    if result is None:
        raise HTTPException(status_code=404, detail=f"no meeting {meeting_id!r}")
    return meeting_shape.detail_out(result, graph=graph)


@app.post("/kt/ingest")
async def kt_ingest(
    repo: Annotated[str, Form()], title: Annotated[str | None, Form()] = None, language: Annotated[str | None, Form()] = None,
    speakers: Annotated[int | None, Form()] = None, audio: Annotated[UploadFile | None, File()] = None,
    transcript: Annotated[UploadFile | None, File()] = None,
) -> Any:
    """Multipart `{repo, title, audio | transcript}` -> `{meeting_id, utterances, decisions, ...}` from `untangle.kt.service`.
    The upload is spooled to a temporary file because the KT functions take paths (Sarvam batch jobs need one)."""
    if audio is None and transcript is None:
        raise HTTPException(status_code=400, detail="send an `audio` file or a `transcript` JSON file")
    upload = audio if audio is not None else transcript
    function = "ingest_audio" if audio is not None else "ingest_transcript"
    ingest = _kt(function)
    suffix = Path(upload.filename or ("audio.wav" if audio is not None else "transcript.json")).suffix or ".bin"
    with tempfile.TemporaryDirectory(prefix="untangle-kt-") as tmp:
        path = Path(tmp) / f"upload{suffix}"
        path.write_bytes(await upload.read())
        name = title or Path(upload.filename or "handover").stem
        if audio is not None:
            return ingest(repo, name, path, language=language, num_speakers=speakers, graph=service.get_graph())
        return ingest(repo, path, title=name, language=language, graph=service.get_graph())


@app.exception_handler(ValidationError)
async def _validation(_: Request, exc: ValidationError) -> JSONResponse:
    return _error(422, "invalid request", details=exc.errors())


__all__ = ["app"]
