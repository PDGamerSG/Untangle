"""Small shared helpers for the answer package: time rendering (epoch ms <-> ISO, human dates), parsing the `at`
argument, and classifying node ids by their deterministic prefix (`pr:`, `commit:`, ...)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

MS_PER_DAY = 86_400_000

# id prefix -> (citation kind, graph label)
_PREFIXES: dict[str, tuple[str, str]] = {
    "dec": ("decision", "Decision"),
    "pr": ("pr", "PullRequest"),
    "issue": ("issue", "Issue"),
    "commit": ("commit", "Commit"),
    "comment": ("comment", "Comment"),
    "doc": ("document", "Document"),
    "utt": ("utterance", "Utterance"),
    "mtg": ("meeting", "Meeting"),
    "person": ("person", "Person"),
    "file": ("file", "File"),
    "module": ("module", "Module"),
    "sym": ("symbol", "Symbol"),
    "cfg": ("config_key", "ConfigKey"),
    "dep": ("dependency", "Dependency"),
    "chunk": ("chunk", "Chunk"),
    "repo": ("repo", "Repo"),
}

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?")
_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1
)}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})
_MONTHS["sept"] = 9


def iso(ms: Any) -> str | None:
    """Epoch milliseconds -> `2023-03-14T10:22:00Z`; None/invalid -> None."""
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000.0, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError, OSError, TypeError):
        return None


def fmt_date(ms: Any) -> str | None:
    """Epoch milliseconds -> `14 Mar 2023` (what the templates print)."""
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000.0, tz=UTC).strftime("%d %b %Y").lstrip("0")
    except (ValueError, OverflowError, OSError, TypeError):
        return None


def date_forms(ms: Any) -> list[str]:
    """Every rendering of a date an answer may legitimately use (for the grounding check)."""
    if ms is None:
        return []
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000.0, tz=UTC)
    except (ValueError, OverflowError, OSError, TypeError):
        return []
    return [
        dt.strftime("%Y-%m-%dT%H:%M:%SZ"), dt.strftime("%Y-%m-%d"), dt.strftime("%d %b %Y").lstrip("0"),
        dt.strftime("%d %B %Y").lstrip("0"), dt.strftime("%b %d %Y"), dt.strftime("%B %d, %Y"), dt.strftime("%b %Y"),
        dt.strftime("%B %Y"), dt.strftime("%Y"), dt.strftime("%d/%m/%Y"), dt.strftime("%m/%d/%Y"),
    ]


def parse_at(value: str | int | float | None, *, end_of_period: bool = False) -> int | None:
    """`2024-01-01`, `2024-01-01T10:00:00Z`, `2024-01`, `2024`, `14 March 2023`, `March 2023` or epoch ms -> epoch ms.
    A bare year or month resolves to its start, or its end with `end_of_period=True` ("what was it in 2022?")."""
    if value is None or value == "":
        return None
    if isinstance(value, int | float):
        return int(value)
    text = str(value).strip()
    if text.isdigit() and len(text) > 4:
        return int(text)
    m = _ISO_DATE.match(text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh, mm, ss = int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0)
        return _ms(datetime(y, mo, d, hh, mm, ss, tzinfo=UTC))
    m = re.match(r"^(\d{4})-(\d{2})$", text)
    if m:
        return _period(int(m.group(1)), int(m.group(2)), end_of_period)
    m = re.match(r"^(\d{4})$", text)
    if m:
        return _period(int(m.group(1)), None, end_of_period)
    m = re.match(r"^(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})$", text)
    if m and m.group(2).lower() in _MONTHS:
        return _ms(datetime(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)), tzinfo=UTC))
    m = re.match(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})$", text)
    if m and m.group(1).lower() in _MONTHS:
        return _ms(datetime(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)), tzinfo=UTC))
    m = re.match(r"^([A-Za-z]{3,9})\.?,?\s+(\d{4})$", text)
    if m and m.group(1).lower() in _MONTHS:
        return _period(int(m.group(2)), _MONTHS[m.group(1).lower()], end_of_period)
    raise ValueError(f"cannot parse date {value!r}; use YYYY-MM-DD")


def _period(year: int, month: int | None, end: bool) -> int:
    if not end:
        return _ms(datetime(year, month or 1, 1, tzinfo=UTC))
    if month is None:
        return _ms(datetime(year + 1, 1, 1, tzinfo=UTC)) - 1
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return _ms(datetime(ny, nm, 1, tzinfo=UTC)) - 1


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def kind_of_id(node_id: str | None) -> str:
    """Citation kind from the id prefix: `pr:owner/name#812` -> `pr`."""
    prefix = (node_id or "").split(":", 1)[0]
    return _PREFIXES.get(prefix, ("node", "Node"))[0]


def label_of(node_id: str | None, labels: list[str] | None = None) -> str:
    """Graph label from the id prefix, falling back to the first non-Incident label returned by Cypher."""
    prefix = (node_id or "").split(":", 1)[0]
    if prefix in _PREFIXES:
        return _PREFIXES[prefix][1]
    for label in labels or []:
        if label != "Incident":
            return label
    return "Node"


def short_sha(sha: str | None, n: int = 7) -> str:
    return (sha or "")[:n]


def squash(text: str | None, limit: int = 320) -> str:
    """Whitespace-normalised excerpt, cut at `limit` characters."""
    out = re.sub(r"\s+", " ", text or "").strip()
    return out if len(out) <= limit else out[: limit - 1].rstrip() + "…"
