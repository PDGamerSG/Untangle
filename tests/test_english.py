"""English rendering of API responses: utterances use `text_en`, other Devanagari is translated once and cached,
identifiers are left alone, and a failing translator never fails the response."""

from __future__ import annotations

import httpx
import pytest

from untangle.answer import service
from untangle.api import english
from untangle.api import main as api
from untangle.api.english import EnglishRenderer, cache_key, collect, prefer_text_en, replace

HINDI = "SES का rate limit hit हो रहा था"
ENGLISH = "The SES rate limit was being hit"


class MemoryStore:
    def __init__(self, seed: dict[str, str] | None = None):
        self.rows = dict(seed or {})
        self.gets = 0
        self.puts: list[dict[str, str]] = []

    def get(self, keys):
        self.gets += 1
        return {k: self.rows[k] for k in keys if k in self.rows}

    def put(self, rows):
        self.puts.extend(rows)
        for r in rows:
            self.rows[r["key"]] = r["en"]


def test_collect_skips_identifiers_and_query_params():
    payload = {
        "id": f"dec:o/r:kt:{HINDI}",
        "url": "https://example.test/" + HINDI,
        "why": {"cypher": [{"params": {"q": HINDI}}]},
        "decision": {"rationale": HINDI, "meeting_id": HINDI},
        "plain": "already English",
    }
    assert collect(payload) == {HINDI}


def test_prefer_text_en_uses_the_stored_translation():
    out = prefer_text_en({"utterances": [{"text": HINDI, "text_en": ENGLISH}, {"text": HINDI, "text_en": None}]})
    assert out["utterances"][0]["text"] == ENGLISH
    assert out["utterances"][1]["text"] == HINDI


def test_replace_keeps_untranslated_strings():
    assert replace({"a": [HINDI, "x"], "id": HINDI}, {HINDI: ENGLISH}) == {"a": [ENGLISH, "x"], "id": HINDI}


def test_renderer_translates_once_then_serves_the_cache():
    calls: list[str] = []
    store = MemoryStore()

    def translate(text):
        calls.append(text)
        return ENGLISH

    r = EnglishRenderer(translate, store)
    payload = {"active": [{"text": HINDI, "rationale": HINDI}]}
    assert r.render(payload) == {"active": [{"text": ENGLISH, "rationale": ENGLISH}]}
    assert calls == [HINDI]
    assert store.puts and store.puts[0]["key"] == cache_key(HINDI) and store.puts[0]["source"] == HINDI

    # A fresh process reads the graph cache instead of calling Sarvam again.
    again = EnglishRenderer(lambda text: pytest.fail("should not translate"), store)
    assert again.render(payload)["active"][0]["text"] == ENGLISH


def test_renderer_leaves_text_when_translation_fails():
    def broken(text):
        raise RuntimeError("sarvam down")

    r = EnglishRenderer(broken, MemoryStore())
    assert r.render({"text": HINDI}) == {"text": HINDI}


def test_renderer_without_translator_uses_cache_only():
    store = MemoryStore({cache_key(HINDI): ENGLISH})
    r = EnglishRenderer(None, store)
    assert r.render({"text": HINDI, "other": "ठीक है"}) == {"text": ENGLISH, "other": "ठीक है"}


def test_renderer_survives_an_unreachable_cache():
    class Down:
        def get(self, keys):
            raise ConnectionError("no graph")

        def put(self, rows):
            raise ConnectionError("no graph")

    r = EnglishRenderer(lambda text: ENGLISH, Down())
    assert r.render({"text": HINDI}) == {"text": ENGLISH}


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as c:
        yield c


async def test_search_endpoint_answers_in_english(client, monkeypatch):
    monkeypatch.setattr(english, "renderer", lambda: EnglishRenderer(lambda text: ENGLISH, MemoryStore()))
    monkeypatch.setattr(service, "search", lambda repo, q: {
        "entities": [{"id": f"cfg:o/r:{HINDI}", "label": "ConfigKey", "name": HINDI, "path": "config.toml", "key": None, "score": 1.0}],
        "people": [],
    })
    r = await client.get("/search", params={"repo": "o/r", "q": "ses"})
    assert r.status_code == 200
    hit = r.json()["entities"][0]
    assert hit["name"] == ENGLISH
    assert hit["id"] == f"cfg:o/r:{HINDI}"


async def test_original_language_can_be_kept(client, monkeypatch):
    monkeypatch.setattr(english, "renderer", lambda: None)
    payload = [{"id": "mtg:o/r:x", "title": HINDI, "utterances": 1, "speakers": 1, "decisions": 0}]
    monkeypatch.setattr(api, "_kt", lambda name: lambda repo, graph: payload)
    monkeypatch.setattr(service, "get_graph", lambda: None)
    r = await client.get("/meetings", params={"repo": "o/r"})
    assert r.status_code == 200
    assert r.json()[0]["title"] == HINDI
