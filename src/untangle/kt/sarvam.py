"""Sarvam AI client for handover calls: speech-to-text (Saaras) for Hindi, Hinglish and English, language
identification and translation.

Two transcription paths, both diarised:

* `transcribe_short` - the synchronous `POST /speech-to-text` endpoint, one clip of at most 30 s (multipart).
* `transcribe_long` / `run_batch_job` - the batch job API (`/speech-to-text/job/v1/...`) for recordings up to a few
  hours: create a job, get signed upload URLs, PUT the audio, start, poll, download the JSON output. The request
  bodies, paths and headers mirror what the `sarvamai` SDK (0.1.40, `client.speech_to_text_job.create_job(...)
  .upload_files(...).start().wait_until_complete().download_outputs(...)`) sends; the SDK's job helper opens its own
  `httpx.Client` for the upload/download legs, so it cannot be driven through an injected transport. Everything here
  goes through ONE `httpx.Client(transport=transport)`, which is what lets the tests replay recorded responses with
  `httpx.MockTransport`, and what makes the real path runnable the moment `SARVAM_API_KEY` is set.

`split_wav_windows` cuts a long WAV into <= 28 s windows for the short endpoint when the batch API is not available
on an account; `transcribe_windows` runs them and shifts the timestamps back onto the recording's timeline.
Speaker labels are then per window (the service numbers speakers afresh in every request).

Retries: 429 and 5xx responses and transport errors are retried with exponential backoff (honouring `Retry-After`).
Any other failure raises `SarvamError` carrying the service's own message. Responses are untrusted data: nothing is
executed, numbers are coerced defensively, and only the documented fields are read.

Docs: https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe (REST),
      https://docs.sarvam.ai/api-reference-docs/speech-to-text-job (batch), /text-lid, /translate."""

from __future__ import annotations

import io
import json
import logging
import mimetypes
import re
import time
import wave
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("kyun.kt.sarvam")

DEFAULT_BASE_URL = "https://api.sarvam.ai"
DEFAULT_STT_MODEL = "saaras:v4"
DEFAULT_TRANSLATE_MODEL = "mayura:v1"  # supports source 'auto' and `mode`; sarvam-translate:v1 allows 2000 chars
SHORT_LIMIT_SECONDS = 30.0
WINDOW_SECONDS = 28.0
MAX_KEYTERMS = 50
TRANSLATE_MAX_CHARS = {"mayura:v1": 1000, "sarvam-translate:v1": 2000}
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=120.0, pool=10.0)
_TERMINAL_STATES = frozenset({"completed", "failed"})
_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


class SarvamError(RuntimeError):
    """The service refused or failed a request. `status` is the HTTP status (None for transport errors)."""

    def __init__(self, message: str, *, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status, self.code = status, code


def _error_message(response: httpx.Response) -> str:
    """Sarvam error bodies look like `{"error": {"message": "...", "code": "..."}}` or `{"detail": ...}`."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err.get("code") or body)[:300]
        if isinstance(err, str):
            return err[:300]
        detail = body.get("detail") or body.get("message")
        if detail:
            return str(detail)[:300]
    return response.text[:300]


def _error_code(response: httpx.Response) -> str | None:
    try:
        err = response.json().get("error")
    except (ValueError, AttributeError):
        return None
    return str(err.get("code")) if isinstance(err, dict) and err.get("code") else None


def mime_for(filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return guessed
    name = filename.lower()
    for ext, mime in ((".wav", "audio/wav"), (".mp3", "audio/mpeg"), (".m4a", "audio/mp4"), (".flac", "audio/flac"), (".ogg", "audio/ogg"), (".webm", "audio/webm")):
        if name.endswith(ext):
            return mime
    return "application/octet-stream"


# ---------- audio helpers ----------


def wav_duration_seconds(audio: bytes) -> float | None:
    """Duration of a WAV container, or None when the bytes are not a WAV file."""
    try:
        with wave.open(io.BytesIO(audio), "rb") as src:
            rate = src.getframerate() or 1
            return src.getnframes() / float(rate)
    except (wave.Error, EOFError, OSError):
        return None


def split_wav_windows(audio_bytes: bytes, seconds: float = WINDOW_SECONDS) -> list[tuple[int, bytes]]:
    """Cut a WAV file into `[(offset_ms, wav_bytes)]` windows of at most `seconds` each, keeping the container's
    channels, sample width and rate. Anything that is not a WAV container comes back whole at offset 0 (the caller
    must keep it under the short endpoint's 30 s limit or use the batch job)."""
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as src:
            params = src.getparams()
            total = src.getnframes()
            per_window = max(1, int(seconds * params.framerate))
            windows: list[tuple[int, bytes]] = []
            pos = 0
            while pos < total:
                src.setpos(pos)
                frames = src.readframes(min(per_window, total - pos))
                out = io.BytesIO()
                with wave.open(out, "wb") as dst:
                    dst.setnchannels(params.nchannels)
                    dst.setsampwidth(params.sampwidth)
                    dst.setframerate(params.framerate)
                    dst.writeframes(frames)
                windows.append((round(pos * 1000 / params.framerate), out.getvalue()))
                pos += per_window
            return windows or [(0, audio_bytes)]
    except (wave.Error, EOFError, OSError):
        return [(0, audio_bytes)]


# ---------- response helpers ----------


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def entries_from_response(resp: Any, *, offset_ms: int = 0) -> list[dict[str, Any]]:
    """Diarised entries `{speaker_id, start_time_seconds, end_time_seconds, transcript}` from a REST response or a
    batch output document, with `offset_ms` added (for windowed transcription). Falls back to `timestamps` chunks
    (one speaker) and finally to the whole `transcript`. A list of documents is concatenated in order."""
    if isinstance(resp, list):
        out: list[dict[str, Any]] = []
        for item in resp:
            out.extend(entries_from_response(item, offset_ms=offset_ms))
        return out
    if not isinstance(resp, dict):
        return []
    shift = offset_ms / 1000.0
    out = []
    diarized = resp.get("diarized_transcript")
    entries = diarized.get("entries") if isinstance(diarized, dict) else None
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        text = str(e.get("transcript") or "").strip()
        if not text:
            continue
        start = _num(e.get("start_time_seconds")) + shift
        end = max(start, _num(e.get("end_time_seconds"), _num(e.get("start_time_seconds"))) + shift)
        out.append({"speaker_id": str(e.get("speaker_id") or "SPEAKER_00"), "start_time_seconds": start, "end_time_seconds": end, "transcript": text})
    if out:
        return out
    stamps = resp.get("timestamps")
    if isinstance(stamps, dict):
        chunks = stamps.get("words") or stamps.get("chunks") or []
        starts, ends = stamps.get("start_time_seconds") or [], stamps.get("end_time_seconds") or []
        for i, chunk in enumerate(chunks if isinstance(chunks, list) else []):
            text = str(chunk or "").strip()
            if not text:
                continue
            start = (_num(starts[i]) if i < len(starts) else 0.0) + shift
            end = max(start, (_num(ends[i]) if i < len(ends) else start - shift) + shift)
            out.append({"speaker_id": "SPEAKER_00", "start_time_seconds": start, "end_time_seconds": end, "transcript": text})
    if out:
        return out
    transcript = str(resp.get("transcript") or "").strip()
    if transcript:
        out.append({"speaker_id": "SPEAKER_00", "start_time_seconds": shift, "end_time_seconds": shift, "transcript": transcript})
    return out


def _sentence_chunks(text: str, limit: int) -> list[str]:
    """Split text at sentence ends so every piece fits the translation input limit."""
    if len(text) <= limit:
        return [text]
    pieces, current = [], ""
    for sentence in _SENTENCE_END.split(text):
        if not sentence:
            continue
        if current and len(current) + 1 + len(sentence) > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
        while len(current) > limit:  # a single run-on sentence longer than the limit: hard cut
            pieces.append(current[:limit])
            current = current[limit:]
    if current:
        pieces.append(current)
    return pieces


# ---------- client ----------


class SarvamClient:
    """Thin, retrying client over Sarvam's REST API. `transport` is forwarded to `httpx.Client` (tests inject
    `httpx.MockTransport`); `sleep` is injectable so retry tests do not wait."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_STT_MODEL,
        mode: str = "codemix",
        transport: httpx.BaseTransport | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout | float | None = None,
        retries: int = 3,
        backoff_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        translate_model: str = DEFAULT_TRANSLATE_MODEL,
    ):
        if not api_key or not api_key.strip():
            raise SarvamError("SARVAM_API_KEY is not configured")
        self.api_key = api_key.strip()
        self.model, self.mode = model, mode
        self.base_url = base_url.rstrip("/")
        self.retries, self.backoff, self._sleep = max(0, int(retries)), float(backoff_seconds), sleep
        self.translate_model = translate_model
        self._http = httpx.Client(transport=transport, timeout=timeout if timeout is not None else _TIMEOUT, follow_redirects=True)
        self.last_request_id: str | None = None

    # -- plumbing --------------------------------------------------------------------------------
    @property
    def headers(self) -> dict[str, str]:
        return {"api-subscription-key": self.api_key}

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> SarvamClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _request(self, method: str, url: str, *, auth: bool = True, expect_json: bool = True, **kwargs: Any) -> Any:
        """One call with retries; returns parsed JSON (or the Response when `expect_json=False`)."""
        if not url.startswith(("http://", "https://")):
            url = f"{self.base_url}/{url.lstrip('/')}"
        headers = dict(kwargs.pop("headers", None) or {})
        if auth:
            headers.update(self.headers)
        last_error: str = "no response"
        for attempt in range(self.retries + 1):
            try:
                response = self._http.request(method, url, headers=headers, **kwargs)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < self.retries:
                    self._backoff(attempt, None)
                    continue
                raise SarvamError(f"Sarvam request failed ({method} {url}): {last_error}") from exc
            if response.status_code in _RETRY_STATUS and attempt < self.retries:
                log.info("Sarvam %s %s returned %s; retrying (%d/%d)", method, url, response.status_code, attempt + 1, self.retries)
                self._backoff(attempt, response.headers.get("Retry-After"))
                continue
            if response.status_code >= 400:
                raise SarvamError(f"Sarvam returned {response.status_code} for {method} {url}: {_error_message(response)}", status=response.status_code, code=_error_code(response))
            if not expect_json:
                return response
            try:
                body = response.json()
            except ValueError as exc:
                raise SarvamError(f"Sarvam returned a non-JSON body for {method} {url}", status=response.status_code) from exc
            if isinstance(body, dict) and body.get("request_id"):
                self.last_request_id = str(body["request_id"])
            return body
        raise SarvamError(f"Sarvam request failed after retries: {last_error}")  # pragma: no cover - defensive

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        delay = self.backoff * (2**attempt)
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass
        self._sleep(min(delay, 60.0))

    # -- speech to text (synchronous, <= 30 s) ---------------------------------------------------
    def transcribe_short(
        self,
        audio_bytes: bytes,
        filename: str,
        *,
        language_code: str | None = None,
        keyterms: Sequence[str] | None = None,
        diarize: bool = True,
        num_speakers: int | None = None,
    ) -> dict[str, Any]:
        """`POST /speech-to-text` (multipart). Returns the raw response: `transcript`, `language_code`, `timestamps`
        and, with diarisation, `diarized_transcript.entries[...]`. `keyterms` (<= 50) bias recognition toward the
        repository's identifiers; the field is only sent for saaras:v4 (the only model that accepts it)."""
        duration = wav_duration_seconds(audio_bytes)
        if duration is not None and duration > SHORT_LIMIT_SECONDS:
            raise SarvamError(f"clip is {duration:.1f} s; the synchronous endpoint takes at most {SHORT_LIMIT_SECONDS:.0f} s (use transcribe_long or transcribe_windows)")
        data: dict[str, str] = {"model": self.model, "mode": self.mode, "with_timestamps": "true"}
        data["language_code"] = language_code or "unknown"
        if diarize:
            data["with_diarization"] = "true"
            if num_speakers:
                data["num_speakers"] = str(int(num_speakers))
        if keyterms and self.model.endswith("v4"):
            data["keyterms"] = json.dumps([str(k) for k in list(keyterms)[:MAX_KEYTERMS]], ensure_ascii=False)
        body = self._request("POST", "speech-to-text", data=data, files={"file": (filename, audio_bytes, mime_for(filename))})
        if not isinstance(body, dict) or not isinstance(body.get("transcript"), str):
            raise SarvamError("speech-to-text response has no transcript")
        return body

    def transcribe_windows(
        self,
        audio_bytes: bytes,
        filename: str,
        *,
        language_code: str | None = None,
        keyterms: Sequence[str] | None = None,
        num_speakers: int | None = None,
        seconds: float = WINDOW_SECONDS,
    ) -> dict[str, Any]:
        """Long WAV through the short endpoint: <= 28 s windows, timestamps shifted back. Returns one document in the
        batch shape (`diarized_transcript.entries`, `language_code`, `windows`). Speaker ids are per window."""
        entries: list[dict[str, Any]] = []
        languages: dict[str, int] = {}
        windows = split_wav_windows(audio_bytes, seconds)
        for offset_ms, chunk in windows:
            body = self.transcribe_short(chunk, filename, language_code=language_code, keyterms=keyterms, diarize=True, num_speakers=num_speakers)
            got = entries_from_response(body, offset_ms=offset_ms)
            entries.extend(got)
            code = body.get("language_code")
            if isinstance(code, str) and got:
                languages[code] = languages.get(code, 0) + sum(len(e["transcript"]) for e in got)
        language = max(languages, key=languages.__getitem__) if languages else None
        return {"transcript": " ".join(e["transcript"] for e in entries), "language_code": language, "diarized_transcript": {"entries": entries}, "windows": len(windows)}

    # -- speech to text (batch job, up to hours) -------------------------------------------------
    def run_batch_job(
        self,
        path: str | Path,
        *,
        language_code: str | None = None,
        keyterms: Sequence[str] | None = None,
        num_speakers: int | None = None,
        poll_interval: float = 5.0,
        timeout: float = 3600.0,
    ) -> dict[str, Any]:
        """Full batch lifecycle for one file; returns the job's output document (JSON) plus `job_id`.

        1. `POST speech-to-text/job/v1` `{job_parameters: {model, mode, with_diarization, with_timestamps, ...}}`
        2. `POST speech-to-text/job/v1/upload-files` `{job_id, files: [name]}` -> signed `upload_urls[name].file_url`
        3. `PUT <signed url>` with the audio bytes (`x-ms-blob-type: BlockBlob`, like the SDK)
        4. `POST speech-to-text/job/v1/<job_id>/start`
        5. `GET speech-to-text/job/v1/<job_id>/status` until `job_state` is Completed or Failed
        6. `POST speech-to-text/job/v1/download-files` `{job_id, files: [output]}` -> signed download URL -> JSON."""
        path = Path(path)
        audio = path.read_bytes()
        name = path.name
        params: dict[str, Any] = {"model": self.model, "mode": self.mode, "with_diarization": True, "with_timestamps": True}
        params["language_code"] = language_code or "unknown"
        if num_speakers:
            params["num_speakers"] = int(num_speakers)
        if keyterms and self.model.endswith("v4"):
            params["keyterms"] = [str(k) for k in list(keyterms)[:MAX_KEYTERMS]]
        init = self._request("POST", "speech-to-text/job/v1", json={"job_parameters": params})
        job_id = str((init or {}).get("job_id") or "")
        if not job_id:
            raise SarvamError("batch job initialisation returned no job_id")
        log.info("Sarvam batch job %s created for %s (%d bytes)", job_id, name, len(audio))

        links = self._request("POST", "speech-to-text/job/v1/upload-files", json={"job_id": job_id, "files": [name]})
        upload = ((links or {}).get("upload_urls") or {}).get(name) or {}
        upload_url = upload.get("file_url") if isinstance(upload, dict) else None
        if not upload_url:
            raise SarvamError(f"batch job {job_id}: no upload URL for {name}")
        self._request("PUT", upload_url, auth=False, expect_json=False, content=audio, headers={"x-ms-blob-type": "BlockBlob", "Content-Type": mime_for(name)})

        self._request("POST", f"speech-to-text/job/v1/{job_id}/start")
        status = self._wait(job_id, poll_interval, timeout)
        if str(status.get("job_state", "")).lower() != "completed":
            raise SarvamError(f"batch job {job_id} {status.get('job_state')}: {status.get('error_message') or 'no message'}")
        output_name = self._output_name(status, name)
        down = self._request("POST", "speech-to-text/job/v1/download-files", json={"job_id": job_id, "files": [output_name]})
        link = ((down or {}).get("download_urls") or {}).get(output_name) or {}
        download_url = link.get("file_url") if isinstance(link, dict) else None
        if not download_url:
            raise SarvamError(f"batch job {job_id}: no download URL for {output_name}")
        response = self._request("GET", download_url, auth=False, expect_json=False)
        try:
            doc = json.loads(response.content.decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise SarvamError(f"batch job {job_id}: output {output_name} is not JSON") from exc
        if isinstance(doc, dict):
            doc.setdefault("job_id", job_id)
        return doc

    def _wait(self, job_id: str, poll_interval: float, timeout: float) -> dict[str, Any]:
        waited = 0.0
        while True:
            status = self._request("GET", f"speech-to-text/job/v1/{job_id}/status")
            state = str((status or {}).get("job_state") or "").lower()
            if state in _TERMINAL_STATES:
                return status
            if waited >= timeout:
                raise SarvamError(f"batch job {job_id} did not finish within {timeout:.0f} s (state {state or 'unknown'})")
            self._sleep(poll_interval)
            waited += poll_interval

    @staticmethod
    def _output_name(status: dict[str, Any], input_name: str) -> str:
        for detail in status.get("job_details") or []:
            if not isinstance(detail, dict):
                continue
            inputs, outputs = detail.get("inputs") or [], detail.get("outputs") or []
            if inputs and outputs and str(detail.get("state", "")).lower() == "success":
                if str((inputs[0] or {}).get("file_name")) == input_name or len(status.get("job_details") or []) == 1:
                    return str((outputs[0] or {}).get("file_name") or f"{input_name}.json")
            if inputs and str(detail.get("state", "")).lower() != "success":
                raise SarvamError(f"batch job failed for {(inputs[0] or {}).get('file_name')}: {detail.get('error_message') or detail.get('state')}")
        return f"{Path(input_name).stem}.json"

    def transcribe_long(
        self,
        path: str | Path,
        *,
        language_code: str | None = None,
        keyterms: Sequence[str] | None = None,
        num_speakers: int | None = None,
        poll_interval: float = 5.0,
        timeout: float = 3600.0,
    ) -> list[dict[str, Any]]:
        """Diarised entries `{speaker_id, start_time_seconds, end_time_seconds, transcript}` of a long recording via
        the batch job API."""
        doc = self.run_batch_job(path, language_code=language_code, keyterms=keyterms, num_speakers=num_speakers, poll_interval=poll_interval, timeout=timeout)
        return entries_from_response(doc)

    # -- text ---------------------------------------------------------------------------------------
    def identify_language(self, text: str) -> dict[str, str | None]:
        """`POST /text-lid` -> `{language_code, script_code}` (e.g. `hi-IN`, `Latn` for Latin-script Hinglish)."""
        body = self._request("POST", "text-lid", json={"input": text[:1000]})
        return {"language_code": body.get("language_code") if isinstance(body, dict) else None, "script_code": body.get("script_code") if isinstance(body, dict) else None}

    def translate(self, text: str, *, source: str = "auto", target: str = "en-IN", mode: str = "code-mixed", model: str | None = None) -> str:
        """`POST /translate` with `mayura:v1` (default) or `sarvam-translate:v1`. Long inputs are split at sentence
        ends to the model's character limit and joined back."""
        model = model or self.translate_model
        limit = TRANSLATE_MAX_CHARS.get(model, 1000)
        parts: list[str] = []
        for piece in _sentence_chunks(text.strip(), limit):
            payload: dict[str, Any] = {"input": piece, "source_language_code": source, "target_language_code": target, "model": model}
            if mode:
                payload["mode"] = mode
            body = self._request("POST", "translate", json=payload)
            translated = body.get("translated_text") if isinstance(body, dict) else None
            if not isinstance(translated, str):
                raise SarvamError("translate response has no translated_text")
            parts.append(translated.strip())
        return " ".join(p for p in parts if p)


__all__ = [
    "DEFAULT_STT_MODEL",
    "SHORT_LIMIT_SECONDS",
    "WINDOW_SECONDS",
    "SarvamClient",
    "SarvamError",
    "entries_from_response",
    "mime_for",
    "split_wav_windows",
    "wav_duration_seconds",
]
