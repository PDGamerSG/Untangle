"""English rendering of API responses: utterances use `text_en`, other Hindi (Devanagari or romanized) is translated
once and cached, identifiers are left alone, partial translations are not kept, and a failing translator never fails
the response."""

from __future__ import annotations

import uuid

import httpx
import pytest

from untangle.answer import service
from untangle.api import english
from untangle.api import main as api
from untangle.api.english import (
    EnglishRenderer,
    cache_key,
    chain,
    collect,
    llm_batch_translator,
    looks_hindi,
    prefer_text_en,
    replace,
)
from untangle.llm import FakeLLM

HINDI = "SES का rate limit hit हो रहा था"
ENGLISH = "The SES rate limit was being hit"
ROMAN = "MAIL-8 abhi bhi Jira mein Blocked hai"


def always(en):
    return lambda texts: [en] * len(texts)


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

    def translate(texts):
        calls.extend(texts)
        return [ENGLISH] * len(texts)

    r = EnglishRenderer(translate, store)
    payload = {"active": [{"text": HINDI, "rationale": HINDI}]}
    assert r.render(payload) == {"active": [{"text": ENGLISH, "rationale": ENGLISH}]}
    assert calls == [HINDI]
    assert store.puts and store.puts[0]["key"] == cache_key(HINDI) and store.puts[0]["source"] == HINDI

    # A fresh process reads the graph cache instead of calling Sarvam again.
    again = EnglishRenderer(lambda texts: pytest.fail("should not translate"), store)
    assert again.render(payload)["active"][0]["text"] == ENGLISH


def test_renderer_leaves_text_when_translation_fails():
    def broken(texts):
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

    r = EnglishRenderer(always(ENGLISH), Down())
    assert r.render({"text": HINDI}) == {"text": ENGLISH}


def test_looks_hindi_covers_romanized_hinglish_but_not_english():
    assert looks_hindi(HINDI)
    assert looks_hindi(ROMAN)
    assert looks_hindi("Haan, comments dekh liye, unpe kaam karungi.")
    for english_text in [
        "Related code changed after this decision was recorded",
        "app.concurrency in schema.sql is 10",
        "who should I ask about internal/manager?",
        "The tab shows the PR from the main branch",
        "Kailash Nadh authored 114 of 133 commits on app.concurrency",
    ]:
        assert not looks_hindi(english_text), english_text


def test_romanized_hinglish_is_translated():
    r = EnglishRenderer(always("MAIL-8 is still blocked in Jira"), MemoryStore())
    assert r.render({"text": ROMAN}) == {"text": "MAIL-8 is still blocked in Jira"}


def test_partial_translations_are_not_used_or_cached():
    store = MemoryStore()
    r = EnglishRenderer(always("Morning. ये Rohan का last full week है।"), store)
    assert r.render({"text": HINDI}) == {"text": HINDI}
    assert store.puts == []


def test_chain_falls_back_for_strings_the_first_translator_left_in_hindi():
    first = lambda texts: [ENGLISH if t == HINDI else t for t in texts]  # noqa: E731 - leaves ROMAN untouched
    second_calls: list[str] = []

    def second(texts):
        second_calls.extend(texts)
        return ["MAIL-8 is still blocked in Jira" for _ in texts]

    assert chain(first, second)([HINDI, ROMAN]) == [ENGLISH, "MAIL-8 is still blocked in Jira"]
    assert second_calls == [ROMAN]


def test_model_translator_batches_and_checks_the_count():
    import json

    reply = json.dumps({"translations": [ENGLISH, "MAIL-8 is still blocked in Jira"]})
    llm = FakeLLM({"MAIL-8": reply})
    assert llm_batch_translator(llm)([HINDI, ROMAN]) == [ENGLISH, "MAIL-8 is still blocked in Jira"]
    short = FakeLLM({"MAIL-8": json.dumps({"translations": [ENGLISH]})})
    assert llm_batch_translator(short)([HINDI, ROMAN]) == [None, None]


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as c:
        yield c


async def test_search_endpoint_answers_in_english(client, monkeypatch):
    monkeypatch.setattr(english, "renderer", lambda: EnglishRenderer(always(ENGLISH), MemoryStore()))
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


@pytest.mark.neo4j
def test_graph_store_round_trips_translations(graph):
    store = english.GraphTranslationStore(graph)
    key = cache_key(f"{HINDI} {uuid.uuid4().hex}")
    try:
        store.put([{"key": key, "en": ENGLISH, "source": HINDI, "at": "2026-10-30T00:00:00Z"}])
        assert store.get([key, "missing"]) == {key: ENGLISH}
    finally:
        graph.query("MATCH (t:Translation {key: $key}) DELETE t", {"key": key})
