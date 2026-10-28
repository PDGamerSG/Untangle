"""Sarvam client against recorded responses through `httpx.MockTransport`: the short endpoint, the batch job
lifecycle, language id, translation, retries and error surfacing. No network, no key."""

from __future__ import annotations

import io
import json
import re
import wave
from typing import Any

import httpx
import pytest

from kyun.kt.sarvam import SarvamClient, SarvamError, entries_from_response, split_wav_windows, wav_duration_seconds

KEY = "test-subscription-key"

SHORT_RESPONSE = {
    "request_id": "req-short-1",
    "transcript": "हमने app.concurrency को 10 पे रखा है। ठीक है।",
    "language_code": "hi-IN",
    "timestamps": {"words": ["हमने app.concurrency को 10 पे रखा है।", "ठीक है।"], "start_time_seconds": [0.2, 4.1], "end_time_seconds": [3.9, 4.9]},
    "diarized_transcript": {
        "entries": [
            {"transcript": "हमने app.concurrency को 10 पे रखा है।", "start_time_seconds": 0.2, "end_time_seconds": 3.9, "speaker_id": "SPEAKER_00"},
            {"transcript": "ठीक है।", "start_time_seconds": 4.1, "end_time_seconds": 4.9, "speaker_id": "SPEAKER_01"},
        ]
    },
}

BATCH_OUTPUT = {
    "transcript": "रोहन शुरू करो। हाँ, config.toml से शुरू करते हैं। ठीक है।",
    "language_code": "hi-IN",
    "diarized_transcript": {
        "entries": [
            {"transcript": "रोहन शुरू करो।", "start_time_seconds": 0.5, "end_time_seconds": 2.0, "speaker_id": "SPEAKER_00"},
            {"transcript": "हाँ, config.toml से शुरू करते हैं।", "start_time_seconds": 2.6, "end_time_seconds": 6.0, "speaker_id": "SPEAKER_01"},
            {"transcript": "ठीक है।", "start_time_seconds": 38.0, "end_time_seconds": 39.0, "speaker_id": "SPEAKER_00"},
        ]
    },
}


def make_wav(seconds: float, rate: int = 8000) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * int(seconds * rate))
    return out.getvalue()


def parse_multipart(request: httpx.Request) -> tuple[dict[str, str], dict[str, tuple[str, bytes, str]]]:
    boundary = request.headers["content-type"].split("boundary=")[1].strip().encode()
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes, str]] = {}
    for part in request.content.split(b"--" + boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        head, _, body = part.partition(b"\r\n\r\n")
        headers = head.decode("utf-8", "replace")
        name = re.search(r'name="([^"]+)"', headers).group(1)
        fm = re.search(r'filename="([^"]*)"', headers)
        if fm:
            cm = re.search(r"content-type:\s*([^\r\n]+)", headers, re.I)
            files[name] = (fm.group(1), body, cm.group(1).strip() if cm else "")
        else:
            fields[name] = body.decode("utf-8")
    return fields, files


def client_for(handler, **kw: Any) -> SarvamClient:
    return SarvamClient(KEY, transport=httpx.MockTransport(handler), sleep=lambda s: None, **kw)


# ---------- short endpoint ----------


def test_transcribe_short_sends_documented_multipart_and_returns_diarized_entries():
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("api-subscription-key")
        seen["fields"], seen["files"] = parse_multipart(request)
        return httpx.Response(200, json=SHORT_RESPONSE)

    wav = make_wav(5)
    with client_for(handler) as c:
        body = c.transcribe_short(wav, "clip.wav", language_code="hi-IN", keyterms=["app.concurrency", "queries.sql"], num_speakers=2)
    assert seen["url"] == "https://api.sarvam.ai/speech-to-text"
    assert seen["key"] == KEY
    f = seen["fields"]
    assert f["model"] == "saaras:v4" and f["mode"] == "codemix" and f["language_code"] == "hi-IN"
    assert f["with_timestamps"] == "true" and f["with_diarization"] == "true" and f["num_speakers"] == "2"
    assert json.loads(f["keyterms"]) == ["app.concurrency", "queries.sql"]
    name, content, ctype = seen["files"]["file"]
    assert name == "clip.wav" and content == wav and ctype.startswith("audio/")
    assert body["transcript"].startswith("हमने")
    entries = entries_from_response(body)
    assert [e["speaker_id"] for e in entries] == ["SPEAKER_00", "SPEAKER_01"]
    assert entries[1]["start_time_seconds"] == 4.1
    assert c.last_request_id == "req-short-1"


def test_transcribe_short_refuses_wav_longer_than_30s_without_calling_the_api():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=SHORT_RESPONSE)

    with client_for(handler) as c, pytest.raises(SarvamError, match="30 s"):
        c.transcribe_short(make_wav(31), "long.wav")
    assert calls == []


def test_keyterms_are_only_sent_for_v4_models():
    seen = {}

    def handler(request):
        seen["fields"], _ = parse_multipart(request)
        return httpx.Response(200, json=SHORT_RESPONSE)

    with client_for(handler, model="saaras:v3") as c:
        c.transcribe_short(make_wav(1), "a.wav", keyterms=["x.y"], diarize=False)
    assert "keyterms" not in seen["fields"] and "with_diarization" not in seen["fields"]
    assert seen["fields"]["model"] == "saaras:v3" and seen["fields"]["language_code"] == "unknown"


# ---------- retries and errors ----------


def test_retries_on_429_and_5xx_then_succeeds_with_backoff():
    attempts: list[int] = []
    sleeps: list[float] = []

    def handler(request):
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, json={"error": {"message": "rate limited"}})
        if len(attempts) == 2:
            return httpx.Response(503, text="upstream busy")
        return httpx.Response(200, json=SHORT_RESPONSE)

    c = SarvamClient(KEY, transport=httpx.MockTransport(handler), sleep=sleeps.append, retries=3, backoff_seconds=0.5)
    body = c.transcribe_short(make_wav(1), "a.wav")
    assert body["language_code"] == "hi-IN"
    assert len(attempts) == 3
    assert sleeps == [2.0, 1.0]  # Retry-After honoured, then exponential backoff (0.5 * 2**1)


def test_gives_up_after_retries_and_surfaces_the_service_message():
    def handler(request):
        return httpx.Response(500, json={"error": {"message": "Internal error, try later", "code": "internal_server_error"}})

    with client_for(handler, retries=1) as c, pytest.raises(SarvamError) as exc:
        c.identify_language("namaste")
    assert exc.value.status == 500 and exc.value.code == "internal_server_error"
    assert "Internal error, try later" in str(exc.value)


def test_client_errors_are_not_retried_and_carry_the_message():
    attempts = []

    def handler(request):
        attempts.append(1)
        return httpx.Response(403, json={"error": {"message": "Invalid API key", "code": "invalid_api_key_error"}})

    with client_for(handler) as c, pytest.raises(SarvamError, match="Invalid API key") as exc:
        c.transcribe_short(make_wav(1), "a.wav")
    assert len(attempts) == 1 and exc.value.status == 403


def test_transport_errors_become_sarvam_errors():
    def handler(request):
        raise httpx.ConnectError("boom")

    with client_for(handler, retries=1) as c, pytest.raises(SarvamError, match="ConnectError"):
        c.translate("hello")


def test_missing_key_is_rejected_early():
    with pytest.raises(SarvamError, match="SARVAM_API_KEY"):
        SarvamClient("   ")


# ---------- batch job ----------


def test_batch_job_lifecycle_mirrors_the_sdk(tmp_path):
    wav = make_wav(40)
    audio_path = tmp_path / "kt.wav"
    audio_path.write_bytes(wav)
    calls: list[str] = []
    status_polls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(f"{request.method} {request.url.host}{path}")
        if request.url.host == "blob.example.net":
            assert "api-subscription-key" not in request.headers
            if request.method == "PUT":
                assert request.headers["x-ms-blob-type"] == "BlockBlob"
                assert request.headers["content-type"].startswith("audio/")
                assert request.content == wav
                return httpx.Response(201)
            assert path == "/kt.json"
            return httpx.Response(200, content=json.dumps(BATCH_OUTPUT, ensure_ascii=False).encode("utf-8"))
        assert request.headers["api-subscription-key"] == KEY
        if path == "/speech-to-text/job/v1" and request.method == "POST":
            params = json.loads(request.content)["job_parameters"]
            assert params["model"] == "saaras:v4" and params["mode"] == "codemix"
            assert params["with_diarization"] is True and params["with_timestamps"] is True
            assert params["language_code"] == "hi-IN" and params["num_speakers"] == 3 and params["keyterms"] == ["app.concurrency"]
            return httpx.Response(200, json={"job_id": "job-1", "job_state": "Accepted", "storage_container_type": "azure", "job_parameters": params})
        if path == "/speech-to-text/job/v1/upload-files":
            assert json.loads(request.content) == {"job_id": "job-1", "files": ["kt.wav"]}
            return httpx.Response(200, json={"job_id": "job-1", "job_state": "Accepted", "storage_container_type": "azure", "upload_urls": {"kt.wav": {"file_url": "https://blob.example.net/kt.wav?sig=1"}}})
        if path == "/speech-to-text/job/v1/job-1/start":
            return httpx.Response(200, json={"job_id": "job-1", "job_state": "Pending", "created_at": "x", "updated_at": "x", "storage_container_type": "azure"})
        if path == "/speech-to-text/job/v1/job-1/status":
            status_polls["n"] += 1
            if status_polls["n"] == 1:
                return httpx.Response(200, json={"job_id": "job-1", "job_state": "Running", "created_at": "x", "updated_at": "x", "storage_container_type": "azure"})
            return httpx.Response(
                200,
                json={
                    "job_id": "job-1", "job_state": "Completed", "created_at": "x", "updated_at": "x", "storage_container_type": "azure",
                    "job_details": [{"inputs": [{"file_name": "kt.wav", "file_id": "in"}], "outputs": [{"file_name": "kt.json", "file_id": "out"}], "state": "Success"}],
                },
            )
        if path == "/speech-to-text/job/v1/download-files":
            assert json.loads(request.content) == {"job_id": "job-1", "files": ["kt.json"]}
            return httpx.Response(200, json={"job_id": "job-1", "job_state": "Completed", "storage_container_type": "azure", "download_urls": {"kt.json": {"file_url": "https://blob.example.net/kt.json?sig=2"}}})
        return httpx.Response(404, json={"error": {"message": f"unexpected {path}"}})

    with client_for(handler) as c:
        entries = c.transcribe_long(audio_path, language_code="hi-IN", keyterms=["app.concurrency"], num_speakers=3, poll_interval=0)
    assert [e["speaker_id"] for e in entries] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]
    assert entries[2]["start_time_seconds"] == 38.0
    assert calls == [
        "POST api.sarvam.ai/speech-to-text/job/v1",
        "POST api.sarvam.ai/speech-to-text/job/v1/upload-files",
        "PUT blob.example.net/kt.wav",
        "POST api.sarvam.ai/speech-to-text/job/v1/job-1/start",
        "GET api.sarvam.ai/speech-to-text/job/v1/job-1/status",
        "GET api.sarvam.ai/speech-to-text/job/v1/job-1/status",
        "POST api.sarvam.ai/speech-to-text/job/v1/download-files",
        "GET blob.example.net/kt.json",
    ]


def test_batch_job_failure_raises_with_the_service_message(tmp_path):
    audio_path = tmp_path / "kt.wav"
    audio_path.write_bytes(make_wav(2))

    def handler(request):
        path = request.url.path
        if path == "/speech-to-text/job/v1":
            return httpx.Response(200, json={"job_id": "job-2", "job_state": "Accepted", "storage_container_type": "azure", "job_parameters": {}})
        if path.endswith("upload-files"):
            return httpx.Response(200, json={"upload_urls": {"kt.wav": {"file_url": "https://blob.example.net/kt.wav"}}})
        if request.url.host == "blob.example.net":
            return httpx.Response(201)
        if path.endswith("/start"):
            return httpx.Response(200, json={"job_state": "Pending"})
        if path.endswith("/status"):
            return httpx.Response(200, json={"job_state": "Failed", "error_message": "unsupported codec"})
        return httpx.Response(404)

    with client_for(handler) as c, pytest.raises(SarvamError, match="unsupported codec"):
        c.run_batch_job(audio_path, poll_interval=0)


# ---------- text ----------


def test_identify_language_and_translate_use_documented_bodies():
    seen: list[dict[str, Any]] = []

    def handler(request):
        body = json.loads(request.content)
        seen.append({"path": request.url.path, "body": body})
        if request.url.path == "/text-lid":
            return httpx.Response(200, json={"request_id": "r1", "language_code": "hi-IN", "script_code": "Latn"})
        return httpx.Response(200, json={"request_id": "r2", "translated_text": f"EN({len(body['input'])})", "source_language_code": "hi-IN"})

    with client_for(handler) as c:
        lid = c.identify_language("humne app.concurrency ko 10 pe rakha hai")
        short = c.translate("humne app.concurrency ko 10 pe rakha hai")
        long_text = ("यह एक वाक्य है जो काफ़ी लंबा है। " * 60).strip()  # > 1000 chars -> split at sentence ends
        joined = c.translate(long_text)
    assert lid == {"language_code": "hi-IN", "script_code": "Latn"}
    assert seen[0]["path"] == "/text-lid" and seen[0]["body"] == {"input": "humne app.concurrency ko 10 pe rakha hai"}
    assert seen[1]["path"] == "/translate"
    assert seen[1]["body"] == {"input": "humne app.concurrency ko 10 pe rakha hai", "source_language_code": "auto", "target_language_code": "en-IN", "model": "mayura:v1", "mode": "code-mixed"}
    assert short == "EN(40)"
    translate_calls = [s for s in seen[2:] if s["path"] == "/translate"]
    assert len(translate_calls) >= 2 and all(len(s["body"]["input"]) <= 1000 for s in translate_calls)
    assert joined.count("EN(") == len(translate_calls)


# ---------- WAV windows ----------


def test_split_wav_windows_cuts_at_28s_and_keeps_offsets():
    wav = make_wav(60, rate=8000)
    windows = split_wav_windows(wav, seconds=28)
    assert [offset for offset, _ in windows] == [0, 28000, 56000]
    assert [round(wav_duration_seconds(chunk)) for _, chunk in windows] == [28, 28, 4]
    assert split_wav_windows(b"not a wav") == [(0, b"not a wav")]


def test_transcribe_windows_shifts_timestamps_back_onto_the_recording():
    seen_durations: list[float] = []

    def handler(request):
        _, files = parse_multipart(request)
        seen_durations.append(wav_duration_seconds(files["file"][1]))
        return httpx.Response(
            200,
            json={
                "transcript": "x", "language_code": "hi-IN",
                "diarized_transcript": {"entries": [{"transcript": "hissa", "start_time_seconds": 1.0, "end_time_seconds": 2.0, "speaker_id": "SPEAKER_00"}]},
            },
        )

    with client_for(handler) as c:
        doc = c.transcribe_windows(make_wav(60), "long.wav")
    assert all(d <= 28 for d in seen_durations) and len(seen_durations) == 3
    assert [e["start_time_seconds"] for e in doc["diarized_transcript"]["entries"]] == [1.0, 29.0, 57.0]
    assert doc["language_code"] == "hi-IN" and doc["windows"] == 3


def test_entries_from_response_falls_back_to_chunks_then_transcript_and_concatenates_lists():
    chunks_only = {"transcript": "a b", "timestamps": {"words": ["a", "b"], "start_time_seconds": [0.0, 1.0], "end_time_seconds": [0.9, 1.9]}}
    got = entries_from_response(chunks_only, offset_ms=10_000)
    assert [(e["speaker_id"], e["start_time_seconds"]) for e in got] == [("SPEAKER_00", 10.0), ("SPEAKER_00", 11.0)]
    assert entries_from_response({"transcript": "sirf text"}) == [{"speaker_id": "SPEAKER_00", "start_time_seconds": 0.0, "end_time_seconds": 0.0, "transcript": "sirf text"}]
    assert len(entries_from_response([SHORT_RESPONSE, BATCH_OUTPUT])) == 5
    assert entries_from_response({"diarized_transcript": {"entries": [{"transcript": "", "speaker_id": "S"}, "junk", {"transcript": "ok", "start_time_seconds": "x"}]}}) == [
        {"speaker_id": "SPEAKER_00", "start_time_seconds": 0.0, "end_time_seconds": 0.0, "transcript": "ok"}
    ]
