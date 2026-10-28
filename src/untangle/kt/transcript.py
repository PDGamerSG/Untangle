"""Transcripts from three sources normalised into one row shape.

* Sarvam responses (REST or batch output): `diarized_transcript.entries[{speaker_id, start_time_seconds,
  end_time_seconds, transcript}]`, else `timestamps` chunks, else the bare `transcript`.
* Untangle's own transcript JSON: `{"title", "language", "started_at", "speakers": {"S1": {"name", "login", "email"}},
  "utterances": [{"speaker": "S1", "start_ms", "end_ms", "text"}]}` (how the sample call in `data/kt/` is written).
* Plain text: `Speaker: text` lines, optionally prefixed with `[mm:ss]`; continuation lines belong to the previous
  speaker. Timestamps are estimated from text length when absent.

`normalise` then merges consecutive entries of the same speaker that are less than 1.5 s apart (Sarvam emits many
short entries per turn) and splits very long entries at sentence ends - `.`, `?`, `!` and the Devanagari danda `।` -
sharing the entry's time span between the sentences in proportion to their length. Transcripts are untrusted input:
every field is coerced, text is whitespace-normalised and control characters are dropped."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MERGE_GAP_MS = 1500
MAX_UTTERANCE_CHARS = 400
MIN_SENTENCE_CHARS = 25
ESTIMATED_MS_PER_CHAR = 70  # ~14 characters per second of speech, used only for text transcripts without timestamps
ESTIMATED_GAP_MS = 400

_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")
_WS = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_TEXT_LINE = re.compile(r"^\s*(?:[\[(](?P<ts>\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)[\])]\s*)?(?P<speaker>[^:\[\]()]{1,60}?)\s*:\s*(?P<text>.+?)\s*$")
_TS_ONLY = re.compile(r"^\s*[\[(](?P<ts>\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)[\])]\s*(?P<text>.+?)\s*$")


@dataclass(slots=True)
class Utterance:
    """One row of a normalised transcript. `speaker_label` is the transcript's own label (`S1`, `SPEAKER_00`)."""

    seq: int
    speaker_label: str
    start_ms: int
    end_ms: int
    text: str
    language: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Transcript:
    """A normalised call: meeting metadata, the speaker map and the utterances in order."""

    utterances: list[Utterance]
    title: str | None = None
    language: str | None = None
    started_at: int | None = None  # epoch ms
    speakers: dict[str, dict[str, str | None]] = field(default_factory=dict)
    source: str = "transcript-json"
    audio_uri: str | None = None
    note: str | None = None

    @property
    def duration_ms(self) -> int:
        return max((u.end_ms for u in self.utterances), default=0)

    @property
    def labels(self) -> list[str]:
        return list(dict.fromkeys(u.speaker_label for u in self.utterances))


# ---------- text helpers ----------


def clean_text(text: Any) -> str:
    return _WS.sub(" ", _CONTROL.sub("", str(text or ""))).strip()


def clean_label(label: Any, default: str = "SPEAKER_00") -> str:
    label = clean_text(label)
    label = re.sub(r"[^\w.-]+", "_", label).strip("_")
    return label or default


def has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI.search(text or ""))


def guess_language(text: str) -> str | None:
    """Script-based guess used only when nothing better is known: Devanagari => `hi-IN`, otherwise unknown (Latin
    script Hinglish and English look the same; Sarvam's text-lid tells them apart)."""
    return "hi-IN" if has_devanagari(text) else None


def split_sentences(text: str, *, min_chars: int = MIN_SENTENCE_CHARS) -> list[str]:
    """Sentences of `text`, split after `.`, `?`, `!` or `।` followed by whitespace; fragments shorter than
    `min_chars` are glued to their neighbour so "Haan." does not become an utterance of its own."""
    parts: list[str] = []
    for piece in _SENTENCE_END.split(clean_text(text)):
        piece = piece.strip()
        if not piece:
            continue
        if parts and (len(piece) < min_chars or len(parts[-1]) < min_chars):
            parts[-1] = f"{parts[-1]} {piece}"
        else:
            parts.append(piece)
    return parts


def parse_started_at(value: Any) -> int | None:
    """ISO-8601 string (naive = UTC) or epoch seconds/milliseconds -> epoch ms."""
    if value is None or value == "":
        return None
    if isinstance(value, int | float):
        n = float(value)
        return int(n if n > 1e11 else n * 1000)
    text = str(value).strip()
    if re.fullmatch(r"\d{10,13}", text):
        return parse_started_at(int(text))
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def _int_ms(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(round(float(value))))
    except (TypeError, ValueError):
        return default


# ---------- normalisation ----------


def _merge(rows: list[Utterance], gap_ms: int) -> list[Utterance]:
    out: list[Utterance] = []
    for row in rows:
        prev = out[-1] if out else None
        if prev and prev.speaker_label == row.speaker_label and row.start_ms - prev.end_ms < gap_ms and row.start_ms >= prev.start_ms:
            prev.text = f"{prev.text} {row.text}".strip()
            prev.end_ms = max(prev.end_ms, row.end_ms)
            prev.language = prev.language or row.language
        else:
            out.append(Utterance(row.seq, row.speaker_label, row.start_ms, row.end_ms, row.text, row.language))
    return out


def _split_long(row: Utterance, max_chars: int) -> list[Utterance]:
    if len(row.text) <= max_chars:
        return [row]
    sentences = split_sentences(row.text)
    if len(sentences) < 2:
        return [row]
    # pack sentences into pieces of at most max_chars (a single longer sentence stays whole)
    pieces: list[str] = []
    for sentence in sentences:
        if pieces and len(pieces[-1]) + 1 + len(sentence) <= max_chars:
            pieces[-1] = f"{pieces[-1]} {sentence}"
        else:
            pieces.append(sentence)
    if len(pieces) < 2:
        return [row]
    span = max(0, row.end_ms - row.start_ms)
    total = sum(len(p) for p in pieces) or 1
    out: list[Utterance] = []
    cursor, consumed = row.start_ms, 0
    for i, piece in enumerate(pieces):
        consumed += len(piece)
        end = row.end_ms if i == len(pieces) - 1 else row.start_ms + span * consumed // total
        out.append(Utterance(row.seq, row.speaker_label, cursor, max(cursor, end), piece, row.language))
        cursor = max(cursor, end)
    return out


def normalise(
    rows: Iterable[Utterance | Mapping[str, Any]],
    *,
    merge_gap_ms: int = MERGE_GAP_MS,
    max_chars: int = MAX_UTTERANCE_CHARS,
    language: str | None = None,
) -> list[Utterance]:
    """Coerce, sort by time, merge same-speaker runs closer than `merge_gap_ms`, split entries longer than
    `max_chars` at sentence ends, and renumber `seq` from 0."""
    coerced: list[Utterance] = []
    for i, r in enumerate(rows):
        if isinstance(r, Utterance):
            u = Utterance(r.seq, clean_label(r.speaker_label), _int_ms(r.start_ms), _int_ms(r.end_ms), clean_text(r.text), r.language)
        else:
            u = Utterance(
                seq=_int_ms(r.get("seq"), i),
                speaker_label=clean_label(r.get("speaker_label") or r.get("speaker") or r.get("speaker_id")),
                start_ms=_int_ms(r.get("start_ms")),
                end_ms=_int_ms(r.get("end_ms")),
                text=clean_text(r.get("text")),
                language=r.get("language"),
            )
        if not u.text:
            continue
        u.end_ms = max(u.end_ms, u.start_ms)
        u.language = u.language or language or guess_language(u.text)
        coerced.append(u)
    coerced.sort(key=lambda u: (u.start_ms, u.end_ms, u.seq))
    merged = _merge(coerced, merge_gap_ms) if merge_gap_ms > 0 else coerced
    out: list[Utterance] = []
    for row in merged:
        out.extend(_split_long(row, max_chars))
    for i, u in enumerate(out):
        u.seq = i
    return out


def as_utterances(rows: Iterable[Utterance | Mapping[str, Any]]) -> list[Utterance]:
    """Coerce rows without merging or splitting (for callers that already normalised); seqs are kept when present."""
    out = normalise(rows, merge_gap_ms=0, max_chars=10**9)
    return out


# ---------- the three inputs ----------


def from_sarvam(doc: Any, *, offset_ms: int = 0, language: str | None = None, source: str = "sarvam-batch", title: str | None = None) -> Transcript:
    """A Sarvam REST response or batch output document (or a list of them) -> Transcript. `speaker_id` becomes the
    speaker label; chunk-only responses get one speaker."""
    from untangle.kt.sarvam import entries_from_response  # local import: keeps this module free of httpx

    entries = entries_from_response(doc, offset_ms=offset_ms)
    code = None
    for item in doc if isinstance(doc, list) else [doc]:
        if isinstance(item, Mapping) and isinstance(item.get("language_code"), str) and item["language_code"] not in ("", "unknown"):
            code = item["language_code"]
            break
    language = language or code
    rows = [
        {"speaker_label": e["speaker_id"], "start_ms": e["start_time_seconds"] * 1000, "end_ms": e["end_time_seconds"] * 1000, "text": e["transcript"]}
        for e in entries
    ]
    utterances = normalise(rows, language=language)
    speakers = {label: {"name": None, "login": None, "email": None} for label in dict.fromkeys(u.speaker_label for u in utterances)}
    return Transcript(utterances=utterances, title=title, language=language, speakers=speakers, source=source)


def _speaker_entry(value: Any) -> dict[str, str | None]:
    if isinstance(value, Mapping):
        return {"name": clean_text(value.get("name")) or None, "login": clean_text(value.get("login")) or None, "email": clean_text(value.get("email")) or None}
    return {"name": clean_text(value) or None, "login": None, "email": None}


def from_untangle_json(obj: Mapping[str, Any]) -> Transcript:
    """Untangle's transcript JSON (see module docstring and `data/kt/README.md`)."""
    if not isinstance(obj, Mapping) or not isinstance(obj.get("utterances"), list):
        raise ValueError("transcript JSON needs an 'utterances' list")
    language = clean_text(obj.get("language")) or None
    speakers = {clean_label(k): _speaker_entry(v) for k, v in (obj.get("speakers") or {}).items()} if isinstance(obj.get("speakers"), Mapping) else {}
    utterances = normalise(obj["utterances"], language=language)
    for label in dict.fromkeys(u.speaker_label for u in utterances):
        speakers.setdefault(label, {"name": None, "login": None, "email": None})
    return Transcript(
        utterances=utterances,
        title=clean_text(obj.get("title")) or None,
        language=language,
        started_at=parse_started_at(obj.get("started_at")),
        speakers=speakers,
        source=clean_text(obj.get("source")) or "transcript-json",
        audio_uri=clean_text(obj.get("audio_uri")) or None,
        note=clean_text(obj.get("_note")) or None,
    )


def _ts_ms(ts: str | None) -> int | None:
    if not ts:
        return None
    main, _, frac = ts.replace(",", ".").partition(".")
    parts = [int(p) for p in main.split(":")]
    seconds = parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0] * 3600 + parts[1] * 60 + parts[2]
    return seconds * 1000 + (int(frac.ljust(3, "0")[:3]) if frac else 0)


def from_text(text: str, *, title: str | None = None, language: str | None = None) -> Transcript:
    """`Speaker: text` lines (optional `[mm:ss]` prefix). Missing timestamps are estimated from text length."""
    raw: list[dict[str, Any]] = []
    names: dict[str, str] = {}
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        m = _TEXT_LINE.match(line)
        if m and not re.match(r"^\s*https?:", line):
            name = clean_text(m.group("speaker"))
            label = names.get(name.lower())
            if label is None:
                label = f"S{len(names) + 1}"
                names[name.lower()] = label
            current = {"speaker_label": label, "speaker_name": name, "start_ms": _ts_ms(m.group("ts")), "text": clean_text(m.group("text"))}
            raw.append(current)
            continue
        t = _TS_ONLY.match(line)
        if current is not None:
            body = clean_text(t.group("text") if t else line)
            current["text"] = f"{current['text']} {body}".strip()
    cursor = 0
    rows: list[dict[str, Any]] = []
    for r in raw:
        start = r["start_ms"] if r["start_ms"] is not None else cursor
        length = max(800, len(r["text"]) * ESTIMATED_MS_PER_CHAR)
        end = start + length
        rows.append({"speaker_label": r["speaker_label"], "start_ms": start, "end_ms": end, "text": r["text"]})
        cursor = end + ESTIMATED_GAP_MS
    for i in range(len(rows) - 1):  # a known next timestamp bounds the estimated end
        if raw[i + 1]["start_ms"] is not None and rows[i]["end_ms"] > rows[i + 1]["start_ms"]:
            rows[i]["end_ms"] = max(rows[i]["start_ms"], rows[i + 1]["start_ms"])
    speakers = {label: {"name": name_key_to_name(raw, label), "login": None, "email": None} for label in names.values()}
    return Transcript(utterances=normalise(rows, language=language), title=title, language=language, speakers=speakers, source="transcript-text")


def name_key_to_name(raw: list[dict[str, Any]], label: str) -> str | None:
    for r in raw:
        if r["speaker_label"] == label:
            return r["speaker_name"]
    return None


def load_transcript(path: str | Path, *, title: str | None = None, language: str | None = None) -> Transcript:
    """Detect the format from the content: Untangle JSON (`utterances`), Sarvam JSON (`diarized_transcript` /
    `timestamps` / `transcript`, or a list of those), otherwise plain text."""
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json" or text.lstrip().startswith(("{", "[")):
        try:
            obj = json.loads(text)
        except ValueError as exc:
            raise ValueError(f"{path} is not valid JSON: {exc}") from exc
        if isinstance(obj, Mapping) and "utterances" in obj:
            t = from_untangle_json(obj)
        elif isinstance(obj, list) or (isinstance(obj, Mapping) and any(k in obj for k in ("diarized_transcript", "timestamps", "transcript"))):
            t = from_sarvam(obj, language=language, source="sarvam-batch", title=title)
        else:
            raise ValueError(f"{path}: unrecognised transcript JSON (expected 'utterances' or a Sarvam response)")
    else:
        t = from_text(text, title=title, language=language)
    if title:
        t.title = title
    if language:
        t.language = language
        for u in t.utterances:
            u.language = u.language or language
    if not t.title:
        t.title = path.stem.replace("-", " ").replace("_", " ")
    return t


__all__ = [
    "MAX_UTTERANCE_CHARS",
    "MERGE_GAP_MS",
    "Transcript",
    "Utterance",
    "as_utterances",
    "clean_label",
    "clean_text",
    "from_untangle_json",
    "from_sarvam",
    "from_text",
    "guess_language",
    "has_devanagari",
    "load_transcript",
    "normalise",
    "parse_started_at",
    "split_sentences",
]
