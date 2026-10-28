"""Router: intents, term extraction, Lucene sanitising, date parsing and match strength. No graph needed."""

from __future__ import annotations

import pytest

from kyun.answer.router import (
    MATCH_THRESHOLD,
    RouterDecision,
    detect_intent,
    extract_mentions,
    lucene_query,
    match_strength,
    route,
)
from kyun.answer.text import fmt_date, iso, parse_at


def test_mentions_cover_paths_keys_identifiers_quotes_and_refs():
    mentions, numbers = extract_mentions('why does internal/mail/sender.go use retry_limit and MaxWorkers from "app.concurrency"? see #812 and PR 790')
    assert "internal/mail/sender.go" in mentions
    assert "sender.go" in mentions
    assert "retry_limit" in mentions
    assert "MaxWorkers" in mentions
    assert "app.concurrency" in mentions
    assert numbers == [812, 790]


def test_mentions_dependency_like_names():
    mentions, _ = extract_mentions("why did we pin @types/node and go-redis and golang.org/x/net?")
    assert "@types/node" in mentions
    assert "go-redis" in mentions
    assert "golang.org/x/net" in mentions


def test_mentions_skip_dates_urls_and_english_hyphens():
    mentions, _ = extract_mentions("what changed on 14/03/2023 side-by-side at https://github.com/x/y?")
    assert "14/03/2023" not in mentions
    assert "side-by-side" not in mentions
    assert not any(m.startswith("http") for m in mentions)


def test_terms_drop_stopwords_and_keep_content_words():
    d = route("Why is the retry limit set to 3 in the mailer?")
    assert "why" not in d.terms and "the" not in d.terms
    assert "retry" in d.terms and "limit" in d.terms and "mailer" in d.terms


def test_lucene_query_is_plain_tokens_with_boosts():
    q = route("why is app.concurrency 10 in config.toml?").lucene
    assert "app^3" in q and "concurrency^3" in q and "config^3" in q
    assert " OR " in q
    for ch in '+-!(){}[]"~*?:\\/':
        assert ch not in q.replace("^3", "")


def test_lucene_query_escapes_and_drops_operators():
    assert lucene_query(["retry", "AND", "a:b", "x*", "or"]) == "retry OR a\\:b OR x\\*"
    assert lucene_query([]) == ""


@pytest.mark.parametrize(
    ("question", "intent"),
    [
        ("why is the retry limit 3?", "why"),
        ("who should I ask about the mailer?", "who_to_ask"),
        ("who knows the SMTP code?", "who_to_ask"),
        ("who owns config.toml?", "who_to_ask"),
        ("what changed in app.concurrency?", "what_changed"),
        ("history of retry_limit", "what_changed"),
        ("do we still cap concurrency at 5?", "is_current"),
        ("is the retry limit still 3?", "is_current"),
        ("list the decisions about config.toml", "list_decisions"),
        ("which decisions were made about the mailer?", "list_decisions"),
        ("what was app.concurrency in March 2023?", "belief_at"),
        ("what was the retry limit as of 2022-05-01?", "belief_at"),
    ],
)
def test_intents(question: str, intent: str):
    assert route(question).intent == intent


def test_at_argument_forces_belief_at_and_parses_dates():
    d = route("why is app.concurrency 10?", at="2022-05-01")
    assert d.intent == "belief_at"
    assert iso(d.at_ms) == "2022-05-01T00:00:00Z"
    assert detect_intent("anything", at="2022-05-01") == "belief_at"


def test_belief_at_date_in_question_resolves_to_end_of_period():
    d = route("what was app.concurrency in March 2023?")
    assert d.intent == "belief_at"
    assert iso(d.at_ms) == "2023-03-31T23:59:59Z"
    assert "2023" not in d.terms and "march" not in d.terms
    assert route("what was it back in 2022?").at_ms == parse_at("2022", end_of_period=True)


def test_belief_at_without_a_parsable_date_falls_back_to_why():
    assert route("what did we believe at the time about retries?").intent == "why"


def test_parse_at_formats():
    assert parse_at("2023-03-14") == parse_at("14 March 2023") == parse_at("Mar 14, 2023")
    assert parse_at("2023-03-14T10:22:00Z") == 1678789320000
    assert parse_at(1678789320000) == 1678789320000
    assert fmt_date(1678789320000) == "14 Mar 2023"
    with pytest.raises(ValueError):
        parse_at("yesterday")


def test_match_strength_exact_and_partial():
    d = route("why is app.concurrency 10 in config.toml?")
    assert match_strength({"label": "ConfigKey", "name": "app.concurrency", "key": "app.concurrency", "path": "config.toml"}, d) == 1.0
    assert match_strength({"label": "File", "name": "config.toml", "path": "config.toml"}, d) == 1.0
    assert match_strength({"label": "File", "name": "config.go", "path": "internal/config.go"}, d) == 0.3  # generic one-token name, not typed verbatim
    assert match_strength({"label": "Module", "name": "sample", "path": "x/sample"}, route('why is "sample" here?')) == 1.0  # typed verbatim (quoted mention)
    partial = match_strength({"label": "File", "name": "concurrency_pool.go", "path": "x/concurrency_pool.go"}, d)
    assert partial == 0.25  # shares only half of the named `app.concurrency`: related, below the anchor threshold
    assert match_strength({"label": "Symbol", "name": "RetryLimit", "path": "a.go"}, d) == 0.0


def test_match_strength_uses_file_name_in_path_mentions():
    d = route("who touched internal/mail/sender.go?")
    assert match_strength({"label": "File", "name": "sender.go", "path": "internal/mail/sender.go"}, d) == 1.0
    assert match_strength({"label": "File", "name": "sender.go", "path": "other/sender.go"}, d) == 1.0


def test_value_tokens_for_is_current():
    d = route("do we still cap concurrency at 5?")
    assert d.value_tokens == ["5"]
    assert route("is retries still true in 2024?").value_tokens == ["true"]


def test_router_decision_is_serialisable():
    d = RouterDecision(intent="why", terms=["a"], lucene="a")
    assert d.to_dict()["intent"] == "why"


def test_one_shared_word_with_a_question_about_something_else_is_not_an_anchor():
    d = route("Why is the GraphQL API rate limited to 50 requests per minute?")
    assert match_strength({"label": "Symbol", "name": "withListAPI", "path": "tests/specs/lists.spec.js"}, d) <= 0.3
    d = route("What is the Redis cache TTL for subscriber lookups?")
    assert match_strength({"label": "Symbol", "name": "Subscriber", "path": "models/subscribers.go"}, d) <= 0.3


def test_identifier_words_outside_the_named_file_still_anchor():
    d = route("why is concurrency 5 in config.toml.sample?")
    assert match_strength({"label": "ConfigKey", "name": "app.concurrency", "key": "app.concurrency", "path": "config.toml.sample"}, d) >= 0.5


def test_camel_case_with_acronym_is_a_mention_and_its_fragment_is_not_a_match():
    d = route("why does listmonk use MongoDB?")
    assert "MongoDB" in d.mentions
    assert match_strength({"label": "Symbol", "name": "resetDB", "path": "cmd/install.go"}, d) < MATCH_THRESHOLD


def test_dependency_named_by_its_short_path():
    d = route("Why does listmonk use lib/pq?")
    assert match_strength({"label": "Dependency", "name": "github.com/lib/pq"}, d) == 1.0


def test_handover_call_questions_set_the_source_and_drop_the_source_words():
    d = route("Why does queries.sql keep raw SQL according to the handover call?")
    assert d.source == "kt" and "handover" not in d.terms and "call" not in d.terms and "sql" in d.terms
    assert route("why is app.concurrency 10?").source is None
