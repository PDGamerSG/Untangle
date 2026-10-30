"""English rendering for API responses.

Handover calls, and the decisions extracted from them, are stored in the language they were spoken in: Hindi or
Hinglish, written in Devanagari or in Latin script ("abhi bhi Jira mein blocked hai"). The web app shows English only,
so every response passes through `EnglishRenderer.render` before it leaves the API:

- an utterance that already has `text_en` shows that as its `text`;
- any other prose that reads as Hindi is translated, and the result is cached in the graph as a
  `(:Translation {key, en})` node, so each sentence is translated once and later requests are fast;
- identifiers, URLs and query parameters are never touched.

Translation uses the configured Claude model in batches (it keeps file paths, config keys and ticket ids intact)
and falls back to Sarvam's formal English. A result is used and cached only when it no longer reads as Hindi, so a
partial translation is retried on a later request instead of being kept.

Set `UNTANGLE_DISPLAY_LANGUAGE=original` to return stored text unchanged."""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel

log = logging.getLogger("untangle.api.english")

DEVANAGARI = re.compile(r"[ऀ-ॿ꣠-ꣿ]")

# Hindi function words and verbs that do not occur as English words. Two or more of them in one string marks it as
# romanized Hindi; ambiguous words such as "to", "me" and "so" are left out on purpose.
_HINGLISH = frozenset(
    """
    hai hain hoon hun tha thi hoga hogi honge kya kyun kyunki kyuki kyonki nahi nahin mein abhi bhi haan han
    gaya gayi gaye liye karna karne karo karenge karega karegi karunga karungi kiya kiye raha rahi rahe wala wali
    wale isliye taaki aur ye yeh woh kuch sab dekh dekho dekhna chal chalo theek thik acha accha achha matlab bas
    bahut kaam aaj jab toh ko ka ki ke pe se ho hua hui mera meri mere tera teri hamara humne hamne maine tumne
    unhe unko usko isko iska uska apna apni wahan yahan kahan kaise kab kaun lekin magar phir agar baad pehle
    zyada jaldi chahiye sakte sakta sakti diya diye lagta lagti batao bata bolo bola boli rakha rakhe rakhna
    """.split()
)
_WORD = re.compile(r"[A-Za-z]+")

# Keys whose values are identifiers, links or query text rather than prose.
_SKIP_KEYS = frozenset({"id", "key", "url", "href", "uri", "audio_uri", "path", "params", "cypher", "label", "kind", "role"})

# Bump when the translation method changes, so earlier cached renderings are not reused.
_CACHE_VERSION = "en-v2"


def looks_hindi(text: str) -> bool:
    """Devanagari, or Latin-script Hinglish."""
    if DEVANAGARI.search(text):
        return True
    words = [w.lower() for w in _WORD.findall(text)]
    if len(words) < 3:
        return False
    hits = [w for w in words if w in _HINGLISH]
    return len(set(hits)) >= 2 and len(hits) >= max(2, 0.18 * len(words))


needs_translation = looks_hindi


def cache_key(text: str) -> str:
    return hashlib.sha1(f"{_CACHE_VERSION}|{text.strip()}".encode()).hexdigest()


def _skip(key: str) -> bool:
    return key in _SKIP_KEYS or key.endswith("_id") or key.endswith("_ids")


def prefer_text_en(obj: Any) -> Any:
    """Use an utterance's stored English rendering as its text."""
    if isinstance(obj, list):
        return [prefer_text_en(v) for v in obj]
    if isinstance(obj, dict):
        out = {k: prefer_text_en(v) for k, v in obj.items()}
        en = out.get("text_en")
        if isinstance(en, str) and en.strip() and not looks_hindi(en) and isinstance(out.get("text"), str):
            out["text"] = en
        return out
    return obj


def collect(obj: Any, found: set[str] | None = None, *, key: str = "") -> set[str]:
    """Every prose string under `obj` that reads as Hindi."""
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not _skip(str(k)):
                collect(v, found, key=str(k))
    elif isinstance(obj, list):
        for v in obj:
            collect(v, found, key=key)
    elif isinstance(obj, str) and looks_hindi(obj):
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


# A batch translator takes source strings and returns one English string (or None) per input, in order.
BatchTranslate = Callable[[Sequence[str]], list[str | None]]


class EnglishRenderer:
    def __init__(self, translate: BatchTranslate | None, store: TranslationStore | None = None, *, memory_limit: int = 5000):
        self.translate = translate
        self.store = store
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
        keys = list(keyed)
        try:
            results = self.translate([keyed[k] for k in keys])  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001 - leave the strings as stored
            log.warning("translation failed: %s", exc)
            return {}
        out: dict[str, str] = {}
        for k, en in zip(keys, results, strict=False):
            en = (en or "").strip()
            if en and not looks_hindi(en):
                out[k] = en
        return out

    def _remember(self, key: str, en: str) -> None:
        with self._lock:
            if len(self._memory) >= self.memory_limit:
                self._memory.clear()
            self._memory[key] = en


# ------------------------------------------------------------------------------------------------------------------
# translators


class _Batch(BaseModel):
    translations: list[str]


_SYSTEM = (
    "You translate notes from software engineering meetings into natural, plain English. The input is a JSON list "
    "of strings in Hindi, Hinglish (Hindi and English mixed), or romanized Hindi. Translate every string fully into "
    "English. Keep exactly as written: code identifiers, file paths, config keys, package names, ticket ids such as "
    "MAIL-12, numbers, dates, people's names and any text in backticks. Do not add or drop information. Reply with "
    'one JSON object {"translations": [...]} holding one English string per input, in the same order.'
)


def llm_batch_translator(llm: Any, *, chunk: int = 25, workers: int = 4) -> BatchTranslate:
    """Claude (or another configured model) translating up to `chunk` strings per request."""
    import json

    def one(texts: Sequence[str]) -> list[str | None]:
        reply = llm.complete_json(_SYSTEM, json.dumps(list(texts), ensure_ascii=False), _Batch, max_tokens=4096)
        if len(reply.translations) != len(texts):
            raise ValueError(f"expected {len(texts)} translations, got {len(reply.translations)}")
        return list(reply.translations)

    def run(texts: Sequence[str]) -> list[str | None]:
        parts = [list(texts[i : i + chunk]) for i in range(0, len(texts), chunk)]

        def safe(part: list[str]) -> list[str | None]:
            try:
                return one(part)
            except Exception as exc:  # noqa: BLE001 - the fallback translator gets these strings
                log.warning("model translation failed for %d strings: %s", len(part), exc)
                return [None] * len(part)

        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(parts)))) as pool:
            return [en for part in pool.map(safe, parts) for en in part]

    return run


def sarvam_batch_translator(client: Any, *, workers: int = 6) -> BatchTranslate:
    """Sarvam's `/translate`, one request per string, in formal English (code-mixed output keeps Hindi words)."""

    def one(text: str) -> str | None:
        try:
            return client.translate(text, source="auto", target="en-IN", mode="formal")
        except Exception as exc:  # noqa: BLE001
            log.warning("sarvam translation failed: %s", exc)
            return None

    def run(texts: Sequence[str]) -> list[str | None]:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(texts)))) as pool:
            return list(pool.map(one, texts))

    return run


def chain(*translators: BatchTranslate) -> BatchTranslate:
    """Try each translator on the strings the previous ones left in Hindi."""

    def run(texts: Sequence[str]) -> list[str | None]:
        out: list[str | None] = [None] * len(texts)
        for translate in translators:
            todo = [i for i, en in enumerate(out) if not en or looks_hindi(en)]
            if not todo:
                break
            try:
                results = translate([texts[i] for i in todo])
            except Exception as exc:  # noqa: BLE001
                log.warning("translator failed: %s", exc)
                continue
            for i, en in zip(todo, results, strict=False):
                if en and en.strip() and not looks_hindi(en):
                    out[i] = en.strip()
        return out

    return run


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

    translators: list[BatchTranslate] = []
    try:
        llm = service.get_llm()
        if llm.available:
            translators.append(llm_batch_translator(llm))
    except Exception as exc:  # noqa: BLE001 - no model configured: Sarvam alone
        log.info("no model for translation: %s", exc)
    if s.sarvam_api_key:
        translators.append(sarvam_batch_translator(SarvamClient(s.sarvam_api_key, timeout=30.0, retries=1)))

    class _LazyStore:
        """Connects on first use so a renderer can exist before the graph is reachable."""

        def get(self, keys: list[str]) -> dict[str, str]:
            return GraphTranslationStore(service.get_graph()).get(keys)

        def put(self, rows: list[dict[str, str]]) -> None:
            GraphTranslationStore(service.get_graph()).put(rows)

    return EnglishRenderer(chain(*translators) if translators else None, _LazyStore())


def to_english(payload: Any) -> Any:
    r = renderer()
    return payload if r is None else r.render(payload)


__all__ = [
    "EnglishRenderer",
    "GraphTranslationStore",
    "chain",
    "collect",
    "llm_batch_translator",
    "looks_hindi",
    "needs_translation",
    "prefer_text_en",
    "renderer",
    "replace",
    "sarvam_batch_translator",
    "to_english",
]
