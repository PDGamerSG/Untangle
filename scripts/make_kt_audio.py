"""Synthesise the sample handover call as audio with Sarvam's Bulbul text-to-speech, one voice per speaker,
laid out on the transcript's own timeline, so the speech-to-text path (Saaras, diarization) can be exercised
end to end without a recorded meeting:

    uv run python scripts/make_kt_audio.py                       # -> data/kt/listmonk-kt-sample.wav
    uv run untangle kt ingest --repo knadh/listmonk --audio data/kt/listmonk-kt-sample.wav --speakers 3 --language hi-IN

Needs SARVAM_API_KEY. A synthetic voice is not a real meeting: use it to test the pipeline, and record a real,
consented handover call for the demo (see data/kt/README.md).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import wave
from pathlib import Path

from untangle.config import PROJECT_ROOT, settings

VOICES = ["shubh", "priya", "kavya", "aditya", "ritu"]  # Bulbul v3 speakers; one per transcript speaker label
RATE = 16_000


def synth(client, text: str, speaker: str, language: str) -> bytes:
    res = client.text_to_speech.convert(  # sarvamai 0.1.40 names the language `language_code`
        text=text, language_code=language, model="bulbul:v3", speaker=speaker, speech_sample_rate=RATE,
    )
    audios = getattr(res, "audios", None) or (res.get("audios") if isinstance(res, dict) else None)
    if not audios:
        raise RuntimeError(f"Bulbul returned no audio for {text[:60]!r}")
    return b"".join(base64.b64decode(a) for a in audios)


def frames_of(wav_bytes: bytes) -> tuple[bytes, int, int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        if w.getframerate() != RATE or w.getnchannels() != 1:
            raise RuntimeError(f"expected {RATE} Hz mono, got {w.getframerate()} Hz x{w.getnchannels()}")
        return w.readframes(w.getnframes()), w.getsampwidth(), w.getnframes()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--transcript", default=str(PROJECT_ROOT / "data" / "kt" / "listmonk-kt-sample.json"))
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data" / "kt" / "listmonk-kt-sample.wav"))
    parser.add_argument("--language", default="hi-IN")
    parser.add_argument("--limit", type=int, default=0, help="only the first N utterances (0 = all)")
    args = parser.parse_args(argv)

    key = settings().sarvam_api_key
    if not key:
        print("SARVAM_API_KEY is not set (add it to .env)", file=sys.stderr)
        return 2
    from sarvamai import SarvamAI

    client = SarvamAI(api_subscription_key=key)
    data = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
    utterances = data["utterances"][: args.limit or None]
    labels = list(dict.fromkeys(u["speaker"] for u in utterances))
    voice = {label: VOICES[i % len(VOICES)] for i, label in enumerate(labels)}

    timeline = bytearray()
    width = 2
    for i, u in enumerate(utterances, 1):
        pcm, width, _ = frames_of(synth(client, u["text"], voice[u["speaker"]], args.language))
        start = int(u.get("start_ms", 0) * RATE / 1000) * width
        if len(timeline) < start:  # keep the transcript's pauses; a long synthetic line simply pushes the next one later
            timeline.extend(b"\x00" * (start - len(timeline)))
        timeline.extend(pcm)
        timeline.extend(b"\x00" * int(0.25 * RATE) * width)
        print(f"  {i}/{len(utterances)} {u['speaker']} ({voice[u['speaker']]}): {len(pcm) / width / RATE:.1f}s", file=sys.stderr)

    out = Path(args.out)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(width)
        w.setframerate(RATE)
        w.writeframes(bytes(timeline))
    print(f"wrote {out} ({len(timeline) / width / RATE:.0f} s, {len(labels)} voices)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
