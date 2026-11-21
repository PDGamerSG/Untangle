"""Public security advisories for dependency versions, from OSV.dev (https://google.github.io/osv.dev/api/).

Pre-flight checks use this to say when a proposed dependency version is affected by an advisory that the current
version is not, and the briefing uses it to explain a past upgrade that fixed one. Only package names, ecosystems
and versions leave the server; OSV needs no key. Every call is bounded by a short timeout and fails soft: callers
get `checked=False` and a note instead of an exception, because advisories add context and never gate an answer.

Versions are checked as written when they are exact (`4.17.21`, `v1.2.3`). A range such as `^4.17.0` is checked at
its lower bound and labelled so, because the installed version depends on a lockfile Untangle may not have."""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("untangle.advisories")

OSV_API = "https://api.osv.dev/v1"
TIMEOUT_S = 4.0
CACHE_TTL_S = 3600.0
MAX_QUERIES = 40
MAX_DETAILS = 12

# Untangle's manifest ecosystems -> OSV ecosystem names.
ECOSYSTEMS = {
    "npm": "npm", "pypi": "PyPI", "go": "Go", "cargo": "crates.io", "maven": "Maven", "rubygems": "RubyGems",
    "packagist": "Packagist", "nuget": "NuGet", "pub": "Pub", "hex": "Hex",
}

_EXACT = re.compile(r"^v?\d+(?:\.\d+){0,3}(?:[-+][0-9A-Za-z.-]+)?$")
_FLOOR = re.compile(r"^(?:\^|~|~=|>=|=>|==|=|>)?\s*(v?\d+(?:\.\d+){0,3}(?:[-+][0-9A-Za-z.-]+)?)\s*(?:,.*|\s*<.*|\s*\|\|.*)?$")


@dataclass(frozen=True)
class Checked:
    """A version in a form OSV accepts, and whether it was written exactly or derived from a range's lower bound."""

    version: str
    exact: bool


def checkable(spec: str | None) -> Checked | None:
    """`4.17.21` -> exact; `^4.17.0` / `>= 0.2.0` / `~=1.4` -> lower bound; `*`, `latest`, git URLs -> None."""
    if not spec:
        return None
    value = spec.strip().strip("\"'")
    if _EXACT.match(value):
        return Checked(value, True)
    match = _FLOOR.match(value)
    if match:
        return Checked(match.group(1), False)
    return None


@dataclass
class Advisory:
    id: str
    summary: str | None = None
    aliases: list[str] = field(default_factory=list)
    published_iso: str | None = None
    url: str | None = None
    severity: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "summary": self.summary, "aliases": self.aliases, "published_iso": self.published_iso,
                "url": self.url, "severity": self.severity}


@dataclass
class Lookup:
    """Advisory ids per (ecosystem, name, version); `checked` is False when OSV could not be reached."""

    checked: bool
    note: str | None = None
    affecting: dict[tuple[str, str, str], list[str]] = field(default_factory=dict)
    details: dict[str, Advisory] = field(default_factory=dict)


_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()


def _cached(key: str) -> Any:
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
            return hit[1]
    return None


def _store(key: str, value: Any) -> None:
    with _cache_lock:
        if len(_cache) > 4000:
            _cache.clear()
        _cache[key] = (time.monotonic(), value)


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def osv_ecosystem(ecosystem: str | None) -> str | None:
    return ECOSYSTEMS.get((ecosystem or "").lower())


def lookup(packages: list[tuple[str, str, str]], *, client: httpx.Client | None = None, enabled: bool = True) -> Lookup:
    """Advisories affecting each `(untangle_ecosystem, name, version)`; versions must already be `checkable`."""
    wanted = [(eco, name, ver) for eco, name, ver in dict.fromkeys(packages) if osv_ecosystem(eco)][:MAX_QUERIES]
    if not wanted:
        return Lookup(checked=True)
    if not enabled:
        return Lookup(checked=False, note="Advisory lookups are turned off on this server.")
    result = Lookup(checked=True)
    missing: list[tuple[str, str, str]] = []
    for item in wanted:
        known = _cached("q|" + "|".join(item))
        if known is None:
            missing.append(item)
        else:
            result.affecting[item] = known
    own = client is None
    http = client or httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": "untangle-preflight"})
    try:
        if missing:
            body = {"queries": [{"package": {"name": name, "ecosystem": osv_ecosystem(eco)}, "version": ver} for eco, name, ver in missing]}
            response = http.post(f"{OSV_API}/querybatch", json=body)
            response.raise_for_status()
            rows = response.json().get("results") or []
            for item, row in zip(missing, rows, strict=False):
                ids = [v["id"] for v in (row or {}).get("vulns") or [] if v.get("id")]
                result.affecting[item] = ids
                _store("q|" + "|".join(item), ids)
        wanted_ids = list(dict.fromkeys(i for ids in result.affecting.values() for i in ids))[:MAX_DETAILS]
        for vid in wanted_ids:
            known = _cached("v|" + vid)
            if known is None:
                response = http.get(f"{OSV_API}/vulns/{vid}")
                response.raise_for_status()
                known = _advisory(response.json())
                _store("v|" + vid, known)
            result.details[vid] = known
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("OSV lookup failed: %s", exc)
        return Lookup(checked=False, note="Public advisories could not be checked right now (OSV.dev did not answer in time).",
                      affecting=result.affecting, details=result.details)
    finally:
        if own:
            http.close()
    return result


def _advisory(row: dict[str, Any]) -> Advisory:
    aliases = [a for a in row.get("aliases") or [] if isinstance(a, str)]
    cve = next((a for a in aliases if a.startswith("CVE-")), None)
    url = f"https://osv.dev/vulnerability/{row.get('id')}"
    severity = None
    database = row.get("database_specific") or {}
    if isinstance(database.get("severity"), str):
        severity = database["severity"].lower()
    summary = row.get("summary") or (row.get("details") or "").strip().split("\n")[0][:240] or None
    return Advisory(id=str(row.get("id")), summary=summary, aliases=([cve] if cve else []) + [a for a in aliases if a != cve][:3],
                    published_iso=row.get("published"), url=url, severity=severity)


__all__ = ["Advisory", "Checked", "ECOSYSTEMS", "Lookup", "checkable", "clear_cache", "lookup", "osv_ecosystem"]
