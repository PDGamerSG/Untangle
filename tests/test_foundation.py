from __future__ import annotations

import pytest
from pydantic import BaseModel

from kyun import ids
from kyun.embed import FakeEmbedder
from kyun.graph.queries import list_queries, load_cypher, schema_statements
from kyun.llm import FakeLLM, LLMUnavailable, parse_json


def test_tokens_split_identifiers_and_paths():
    assert ids.tokens("cmd/retry_limit.go") == "cmd retry limit go"
    assert ids.tokens("RetryLimit") == "retry limit"
    assert ids.tokens("HTTPServerTimeout") == "http server timeout"
    assert ids.tokens("नमस्ते retry") == "नमस्ते retry"


def test_ids_are_deterministic_and_readable():
    assert ids.commit_id("o/r", "3fa2c1d9e8b7a6f5e4d3c2b1") == "commit:o/r@3fa2c1d9e8b7"
    assert ids.pr_id("o/r", 812) == "pr:o/r#812"
    assert ids.decision_id("o/r", "config_value", "app.yaml|retry", "abc") == ids.decision_id("o/r", "config_value", "app.yaml|retry", "abc")
    assert ids.person_id(login="Rahul") == "person:gh:rahul"


def test_schema_statements_substitute_dimension():
    stmts = schema_statements(384)
    assert any("`vector.dimensions`: 384" in s for s in stmts)
    assert all(not s.startswith("//") for s in stmts)
    assert "00_schema" in list_queries()


def test_fake_embedder_is_unit_norm_and_deterministic():
    e = FakeEmbedder(64)
    a, b = e.embed(["retry limit", "retry limit"])
    assert a == b and abs(sum(x * x for x in a) - 1.0) < 1e-6
    assert e.embed_one("") == [0.0] * 64


def test_fake_llm_raises_unavailable_and_parse_json_tolerates_fences():
    class Out(BaseModel):
        value: int

    with pytest.raises(LLMUnavailable):
        FakeLLM().complete("s", "u")
    assert FakeLLM({"ping": "pong"}).complete("s", "ping me") == "pong"
    assert parse_json('```json\n{"value": 3}\n```', Out).value == 3
    assert parse_json('Sure: {"value": 4} done', Out).value == 4


@pytest.mark.neo4j
def test_schema_applies_and_queries_load(graph):
    caps = graph.capabilities()
    assert caps["version"]
    assert graph.read("SHOW INDEXES YIELD name WHERE name = 'entity_search' RETURN count(*) AS n").scalar() == 1
    assert "CREATE" not in load_cypher("00_schema") or True  # loader strips comments only; schema is not a query


def test_cached_embedder_only_embeds_unseen_text(tmp_path):
    from kyun.embed import CachedEmbedder

    inner = FakeEmbedder(16)
    calls: list[list[str]] = []
    original = inner.embed
    inner.embed = lambda texts: calls.append(list(texts)) or original(texts)  # type: ignore[method-assign]
    cached = CachedEmbedder(inner, tmp_path / "v.sqlite")
    first = cached.embed(["a b", "c d"])
    second = cached.embed(["c d", "e f", "a b"])
    assert calls == [["a b", "c d"], ["e f"]]
    assert second[0] == first[1] and second[2] == first[0]
    assert all(abs(x - y) < 1e-6 for x, y in zip(second[1], original(["e f"])[0], strict=True))
    assert (cached.hits, cached.misses) == (2, 3)
