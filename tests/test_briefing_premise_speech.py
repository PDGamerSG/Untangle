"""Day-one briefing and premise checks against the fixture graph; speech with a mock Sarvam transport."""

from __future__ import annotations

import base64
import json
import uuid

import httpx
import pytest

from _answer_fixture import Fixture, seed_graph, unseed_people
from untangle import speech
from untangle.answer import service
from untangle.answer.premise import comparison
from untangle.briefing import briefing, briefing_markdown
from untangle.kt.sarvam import SarvamClient, SarvamError


@pytest.fixture(scope="module")
def fx(graph):
    suffix = uuid.uuid4().hex[:6]
    repo = f"test/brief{suffix}"
    fixture = seed_graph(graph, repo, suffix=suffix)
    graph.query(
        """MATCH (f:File {repo: $repo, path: 'config.toml'})
        CREATE (d:Dependency {id: $repo + ':dep:mocha', repo: $repo, name: 'mocha', ecosystem: 'npm', current_version: '^3.5.3'})-[:DECLARED_IN]->(f)""",
        {"repo": repo},
    )
    yield fixture
    unseed_people(graph, fixture)
    graph.wipe_repo(repo)


@pytest.mark.neo4j
def test_briefing_lists_areas_guarded_decisions_changes_and_people(graph, fx: Fixture):
    b = briefing(fx.repo, graph=graph)
    areas = {a.name: a for a in b.areas}
    assert set(areas) == {"(root)", "internal/mail"}  # `internal` is a container directory
    assert areas["(root)"].commits == 2 and areas["(root)"].people[0].login == fx.login and areas["(root)"].people[0].share == 1.0
    assert areas["(root)"].decisions == 1  # the active decision about config.toml and its key, counted once
    assert b.guarded[0].decision.id == fx.dec_new and b.guarded[0].guards[0].startswith("Introduced after incident #790")
    assert b.changes[0].newer.id == fx.dec_new and b.changes[0].older.id == fx.dec_old and b.changes[0].at_iso.startswith("2023-03-14")
    assert b.people[0].login == fx.login and "(root)" in b.people[0].areas
    assert any("app.concurrency" in q for q in b.questions)
    md = briefing_markdown(b)
    assert "## Read before changing" in md and "incident #790" in md and "| (root) | 1 | 2 |" in md
    with pytest.raises(service.NotFound):
        briefing("test/not-there-at-all", graph=graph)


@pytest.mark.parametrize(("question", "pair"), [
    ("Why is Mocha used instead of Jest?", ("Mocha", "Jest")),
    ("why do we use kafka over rabbitmq", ("kafka", "rabbitmq")),
    ("Why redis rather than memcached?", ("redis", "memcached")),
    ("why is it 10 instead of 5", None),
    ("why 10 instead of 5", None),
    ("What changed in app.concurrency?", None),
])
def test_comparison_questions(question, pair):
    assert comparison(question) == pair


@pytest.mark.neo4j
def test_ask_reports_a_reversed_premise(graph, fx: Fixture):
    reversed_ = service.ask("Why do we use jest instead of mocha?", fx.repo, graph=graph)
    assert reversed_.premise and reversed_.premise.status == "contradicted" and "`mocha` at `^3.5.3`" in reversed_.premise.text
    holds = service.ask("Why is mocha used instead of jest?", fx.repo, graph=graph)
    assert holds.premise and holds.premise.status == "consistent"
    neither = service.ask("Why kafka over rabbitmq?", fx.repo, graph=graph)
    assert neither.premise and neither.premise.status == "unsupported"
    assert service.ask("why is app.concurrency 10?", fx.repo, graph=graph).premise is None


# -- speech --------------------------------------------------------------------------------------------------------------


def test_speakable_removes_citations_and_markdown():
    text = "`app.concurrency` is 10 [dec:o/r:config_value:1]. See [PR #812](https://x) **now** [pr:o/r#812]."
    assert speech.speakable(text) == "app.concurrency is 10. See PR 812 now."  # "#" would be read aloud as "hash"


def _sarvam(calls: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append({"path": request.url.path, **body})
        assert request.headers["api-subscription-key"] == "test-key"
        if request.url.path.endswith("/translate"):
            return httpx.Response(200, json={"translated_text": "app.concurrency 10 है।"})
        return httpx.Response(200, json={"audios": [base64.b64encode(b"ID3fake").decode()]})

    return SarvamClient("test-key", transport=httpx.MockTransport(handler), retries=0)


def test_speak_translates_then_reads_aloud():
    calls: list[dict] = []
    out = speech.speak("`app.concurrency` is 10 [dec:o/r:x].", "hi-IN", client=_sarvam(calls))
    assert out.text == "app.concurrency 10 है।" and base64.b64decode(out.audio_base64) == b"ID3fake" and out.mime == "audio/mpeg"
    assert calls[0]["path"] == "/translate" and calls[0]["input"] == "app.concurrency is 10." and calls[0]["target_language_code"] == "hi-IN"
    assert calls[1]["path"] == "/text-to-speech" and calls[1]["language_code"] == "hi-IN" and calls[1]["output_audio_codec"] == "mp3"


def test_speak_in_english_skips_translation_and_validates_input():
    calls: list[dict] = []
    speech.speak("Hello there.", "en-IN", client=_sarvam(calls))
    assert [c["path"] for c in calls] == ["/text-to-speech"]
    with pytest.raises(ValueError):
        speech.speak("Hello", "xx-XX", client=_sarvam([]))
    with pytest.raises(ValueError):
        speech.speak("[dec:o/r:x]", "hi-IN", client=_sarvam([]))


async def test_speak_endpoint_without_a_key_is_unavailable(monkeypatch):
    from untangle.api import main as api

    def fail(*args, **kwargs):
        raise SarvamError("SARVAM_API_KEY is not set")

    monkeypatch.setattr(speech, "speak", fail)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://untangle.test") as client:
        r = await client.post("/speak", json={"text": "hello", "language": "hi-IN"})
        assert r.status_code == 503 and "Listening is unavailable" in r.json()["error"]
        langs = (await client.get("/speak/languages")).json()
        assert {"code": "ta-IN", "name": "தமிழ் (Tamil)"} in langs["languages"]
