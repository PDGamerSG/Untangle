"""English rendering for API responses.

Handover calls, and the decisions extracted from them, are stored in the language they were spoken in, which is
often Hindi or Hinglish written in Devanagari. The web app shows English only, so every response passes through
`EnglishRenderer.render` before it leaves the API:

- an utterance that already has `text_en` shows that as its `text`;
- any other string containing Devanagari is translated with Sarvam and the result is cached in the graph as a
  `(:Translation {key, en})` node, so each sentence is translated once and later requests are fast;
- identifiers, URLs and query parameters are never touched.

Set `UNTANGLE_DISPLAY_LANGUAGE=original` to return stored text unchanged. Without a Sarvam key the renderer still
uses cached translations and leaves anything uncached as stored."""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Protocol

log = logging.getLogger("untangle.api.english")

DEVANAGARI = re.compile(r"[ऀ-ॿ꣠-ꣿ]")

# Keys whose values are identifiers, links or query text rather than prose.
_SKIP_KEYS = frozenset({"id", "key", "url", "href", "uri", "audio_uri", "path", "params", "cypher", "label", "kind", "role"})


def needs_translation(text: str) -> bool:
    return bool(DEVANAGARI.search(text))


def cache_key(text: str) -> str:
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()


def _skip(key: str) -> bool:
    return key in _SKIP_KEYS or key.endswith("_id") or key.endswith("_ids")


def prefer_text_en(obj: Any) -> Any:
    """Use an utterance's stored English rendering as its text."""
    if isinstance(obj, list):
        return [prefer_text_en(v) for v in obj]
    if isinstance(obj, dict):
        out = {k: prefer_text_en(v) for k, v in obj.items()}
        en = out.get("text_en")
        if isinstance(en, str) and en.strip() and isinstance(out.get("text"), str):
            out["text"] = en
        return out
    return obj


def collect(obj: Any, found: set[str] | None = None, *, key: str = "") -> set[str]:
    """Every prose string under `obj` that contains Devanagari."""
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not _skip(str(k)):
                collect(v, found, key=str(k))
    elif isinstance(obj, list):
        for v in obj:
            collect(v, found, key=key)
    elif isinstance(obj, str) and needs_translation(obj):
        found.add(obj)
    return found


def replace(obj: Any, english: Mapping[str, str]) -> Any:
    if isinstance(obj, dict):
        return {k: (v if _skip(str(k)) else replace(v, english)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [replace(v, english) for v in obj]
    if isinstance(obj, str):
        return english.get(obj, obj)
    return obj


class TranslationStore(Protocol):
    def get(self, keys: list[str]) -> dict[str, str]: ...

    def put(self, rows: list[dict[str, str]]) -> None: ...


class GraphTranslationStore:
    """`(:Translation {key, en})` nodes, read and written with the named Cypher in `cypher/`."""

    def __init__(self, graph: Any):
        self.graph = graph

    def get(self, keys: list[str]) -> dict[str, str]:
        if not keys:
            return {}
        rows = self.graph.run_named("translations_get", {"keys": keys}).records
        return {r["key"]: r["en"] for r in rows if r.get("en")}

    def put(self, rows: list[dict[str, str]]) -> None:
        if rows:
            self.graph.run_named("translations_put", {"rows": rows}, write=True)


class EnglishRenderer:
    def __init__(
        self,
        translate: Callable[[str], str] | None,
        store: TranslationStore | None = None,
        *,
        max_workers: int = 8,
        memory_limit: int = 5000,
    ):
        self.translate = translate
        self.store = store
        self.max_workers = max_workers
        self.memory_limit = memory_limit
        self._memory: dict[str, str] = {}
        self._lock = threading.Lock()

    def render(self, payload: Any) -> Any:
        payload = prefer_text_en(payload)
        texts = collect(payload)
        if not texts:
            return payload
        return replace(payload, self.english_for(texts))

    def english_for(self, texts: Iterable[str]) -> dict[str, str]:
        keyed = {cache_key(t): t for t in texts}
        english: dict[str, str] = {}
        with self._lock:
            for k in list(keyed):
                if k in self._memory:
                    english[keyed.pop(k)] = self._memory[k]
        if keyed and self.store is not None:
            try:
                cached = self.store.get(list(keyed))
            except Exception as exc:  # noqa: BLE001 - a cache miss must not fail the response
                log.warning("translation cache unavailable: %s", exc)
                cached = {}
            for k, en in cached.items():
                english[keyed.pop(k)] = en
                self._remember(k, en)
        if keyed and self.translate is not None:
            fresh = self._translate_all(keyed)
            for k, en in fresh.items():
                english[keyed[k]] = en
                self._remember(k, en)
            if fresh and self.store is not None:
                now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
                try:
                    self.store.put([{"key": k, "en": en, "source": keyed[k], "at": now} for k, en in fresh.items()])
                except Exception as exc:  # noqa: BLE001
                    log.warning("could not cache translations: %s", exc)
        return english

    def _translate_all(self, keyed: Mapping[str, str]) -> dict[str, str]:
        def one(item: tuple[str, str]) -> tuple[str, str | None]:
            k, text = item
            try:
                en = (self.translate(text) or "").strip()  # type: ignore[misc]
            except Exception as exc:  # noqa: BLE001 - leave this one string as stored
                log.warning("translation failed: %s", exc)
                return k, None
            return k, en or None

        with ThreadPoolExecutor(max_workers=max(1, min(self.max_workers, len(keyed)))) as pool:
            results = list(pool.map(one, keyed.items()))
        return {k: en for k, en in results if en}

    def _remember(self, key: str, en: str) -> None:
        with self._lock:
            if len(self._memory) >= self.memory_limit:
                self._memory.clear()
            self._memory[key] = en


_renderer: EnglishRenderer | None = None
_renderer_lock = threading.Lock()


def renderer() -> EnglishRenderer | None:
    """The process-wide renderer, or None when the display language is `original`."""
    global _renderer
    from untangle.config import settings

    s = settings()
    if s.display_language != "en":
        return None
    with _renderer_lock:
        if _renderer is None:
            _renderer = _build(s)
        return _renderer


def _build(s: Any) -> EnglishRenderer:
    from untangle.answer import service
    from untangle.kt.sarvam import SarvamClient

    translate: Callable[[str], str] | None = None
    if s.sarvam_api_key:
        client = SarvamClient(s.sarvam_api_key, timeout=30.0, retries=1)
        translate = lambda text: client.translate(text, source="auto", target="en-IN", mode="code-mixed")  # noqa: E731

    class _LazyStore:
        """Connects on first use so a renderer can exist before the graph is reachable."""

        def get(self, keys: list[str]) -> dict[str, str]:
            return GraphTranslationStore(service.get_graph()).get(keys)

        def put(self, rows: list[dict[str, str]]) -> None:
            GraphTranslationStore(service.get_graph()).put(rows)

    return EnglishRenderer(translate, _LazyStore())


def to_english(payload: Any) -> Any:
    r = renderer()
    return payload if r is None else r.render(payload)


__all__ = ["EnglishRenderer", "GraphTranslationStore", "collect", "needs_translation", "prefer_text_en", "renderer", "replace", "to_english"]
