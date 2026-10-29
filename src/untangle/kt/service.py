"""Service layer for handover calls, used by the CLI (`untangle kt ...`) and the API (`/meetings`, `/kt/ingest`).

* `meetings(repo)` / `meeting(id)` read the graph (`45_kt_meetings`, `46_kt_meeting_detail`).
* `ingest_transcript(repo, path)` loads a Untangle / Sarvam / plain-text transcript and runs `ingest_kt`.
* `ingest_audio(repo, title, path)` transcribes with Sarvam first: the synchronous endpoint for WAV clips of at
  most 30 s, the batch job for everything longer (and for compressed formats whose duration is unknown), and the
  28 s window fallback through the short endpoint when the batch API is not available on the account.

The Sarvam client, LLM, embedder and graph are injectable so everything runs offline against fakes; the defaults
come from `untangle.config.settings()` (`SARVAM_API_KEY`, `LLM_BACKEND`, `EMBED_BACKEND`, `NEO4J_*`)."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from untangle.config import Settings, settings
from untangle.embed import Embedder
from untangle.graph.db import Graph, connect
from untangle.kt.pipeline import ingest_kt, keyterms_for_repo
from untangle.kt.sarvam import SHORT_LIMIT_SECONDS, SarvamClient, SarvamError, wav_duration_seconds
from untangle.kt.transcript import Transcript, from_sarvam, load_transcript
from untangle.llm import LLM, make_llm

log = logging.getLogger("untangle.kt.service")

SHORT_FILE_BYTES = 1_000_000  # a compressed file this small is almost certainly under 30 s


def iso(ms: int | float | None) -> str | None:
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(float(ms) / 1000.0, tz=UTC).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return None


def sarvam_client(s: Settings | None = None, *, transport: httpx.BaseTransport | None = None) -> SarvamClient | None:
    """A `SarvamClient` from settings, or None when `SARVAM_API_KEY` is not set."""
    s = s or settings()
    if not s.sarvam_api_key:
        return None
    return SarvamClient(s.sarvam_api_key, model=s.sarvam_stt_model, mode=s.sarvam_stt_mode, transport=transport)


@contextmanager
def _graph(graph: Graph | None) -> Iterator[Graph]:
    if graph is not None:
        yield graph
        return
    g = connect(require=True)
    try:
        yield g
    finally:
        g.close()


# ---------- reads ----------


def meetings(repo: str, *, graph: Graph | None = None) -> list[dict[str, Any]]:
    with _graph(graph) as g:
        rows = g.run_named("kt_meetings", {"repo": repo}).records
    for r in rows:
        r["started_at_iso"] = iso(r.get("started_at"))
    return rows


def meeting(meeting_id: str, *, graph: Graph | None = None) -> dict[str, Any] | None:
    with _graph(graph) as g:
        rows = g.run_named("kt_meeting_detail", {"id": meeting_id}).records
    if not rows:
        return None
    m = rows[0]
    m["started_at_iso"] = iso(m.get("started_at"))
    for d in m.get("decisions") or []:
        d["valid_from_iso"] = iso(d.get("valid_from"))
        d["valid_to_iso"] = iso(d.get("valid_to"))
    return m


# ---------- transcription ----------


def transcribe_audio(
    client: SarvamClient,
    audio_path: str | Path,
    *,
    language: str | None = None,
    num_speakers: int | None = None,
    keyterms: Sequence[str] | None = None,
    prefer_windows: bool = False,
    title: str | None = None,
) -> Transcript:
    """Pick the Sarvam path for this file and return a normalised transcript (`source` says which path ran)."""
    path = Path(audio_path)
    audio = path.read_bytes()
    if not audio:
        raise SarvamError(f"{path} is empty")
    duration = wav_duration_seconds(audio)
    if duration is not None and duration <= SHORT_LIMIT_SECONDS:
        doc = client.transcribe_short(audio, path.name, language_code=language, keyterms=keyterms, diarize=True, num_speakers=num_speakers)
        return from_sarvam(doc, language=language, source="sarvam-rest", title=title)
    if prefer_windows and duration is not None:
        doc = client.transcribe_windows(audio, path.name, language_code=language, keyterms=keyterms, num_speakers=num_speakers)
        return from_sarvam(doc, language=language, source="sarvam-rest", title=title)
    try:
        doc = client.run_batch_job(path, language_code=language, keyterms=keyterms, num_speakers=num_speakers)
        return from_sarvam(doc, language=language, source="sarvam-batch", title=title)
    except SarvamError as exc:
        if duration is not None:
            log.warning("batch job failed (%s); falling back to 28 s windows through the short endpoint", exc)
            doc = client.transcribe_windows(audio, path.name, language_code=language, keyterms=keyterms, num_speakers=num_speakers)
            return from_sarvam(doc, language=language, source="sarvam-rest", title=title)
        if len(audio) <= SHORT_FILE_BYTES:
            log.warning("batch job failed (%s); trying the short endpoint for the small %s", exc, path.name)
            doc = client.transcribe_short(audio, path.name, language_code=language, keyterms=keyterms, diarize=True, num_speakers=num_speakers)
            return from_sarvam(doc, language=language, source="sarvam-rest", title=title)
        raise


# ---------- ingestion ----------


def ingest_transcript(
    repo: str,
    path: str | Path,
    *,
    title: str | None = None,
    language: str | None = None,
    translate: bool = True,
    graph: Graph | None = None,
    llm: LLM | None = None,
    embedder: Embedder | None = None,
    sarvam: SarvamClient | None = None,
) -> dict[str, Any]:
    """Load a transcript file (Untangle JSON, Sarvam JSON or `Speaker: text` lines) into the graph."""
    t = load_transcript(path, title=title, language=language)
    client = sarvam if sarvam is not None else (sarvam_client() if translate else None)
    with _graph(graph) as g:
        return ingest_kt(
            g, repo, title=t.title or Path(path).stem, utterances=t.utterances, speakers=t.speakers, started_at=t.started_at,
            language=t.language, audio_uri=t.audio_uri, llm=llm if llm is not None else make_llm(), embedder=embedder,
            source=t.source, sarvam=client, translate=translate, summary=t.note,
        )


def ingest_audio(
    repo: str,
    title: str,
    audio_path: str | Path,
    *,
    language: str | None = None,
    num_speakers: int | None = None,
    translate: bool = True,
    graph: Graph | None = None,
    llm: LLM | None = None,
    embedder: Embedder | None = None,
    sarvam: SarvamClient | None = None,
    keyterms: Sequence[str] | None = None,
    prefer_windows: bool = False,
    started_at: int | str | None = None,
) -> dict[str, Any]:
    """Transcribe a recording with Sarvam (keyterms biased toward the repository's identifiers) and ingest it."""
    client = sarvam if sarvam is not None else sarvam_client()
    if client is None:
        raise SarvamError("SARVAM_API_KEY is not set; transcribe elsewhere and use --transcript, or set the key")
    with _graph(graph) as g:
        terms = list(keyterms) if keyterms is not None else _safe_keyterms(g, repo)
        t = transcribe_audio(client, audio_path, language=language, num_speakers=num_speakers, keyterms=terms, prefer_windows=prefer_windows, title=title)
        return ingest_kt(
            g, repo, title=title, utterances=t.utterances, speakers=t.speakers, started_at=started_at, language=t.language or language,
            audio_uri=None, llm=llm if llm is not None else make_llm(), embedder=embedder, source=t.source,
            sarvam=client, translate=translate,
        )


def _safe_keyterms(graph: Graph, repo: str) -> list[str]:
    try:
        return keyterms_for_repo(graph, repo)
    except Exception as exc:  # noqa: BLE001 - keyterms only bias recognition; never block ingestion
        log.warning("keyterms unavailable for %s: %s", repo, exc)
        return []


__all__ = ["ingest_audio", "ingest_transcript", "iso", "meeting", "meetings", "sarvam_client", "transcribe_audio"]
