"""Decision extraction (heuristic and LLM paths), entity matching, and the end-to-end KT ingestion on a real Neo4j."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pytest

from kyun import ids
from kyun.kt.extract import extract_decisions, extract_heuristic, extract_with_llm
from kyun.kt.pipeline import (
    EntityRef,
    Matcher,
    build_aliases,
    decision_sentence,
    guard_ok,
    ingest_kt,
    keyterms_for_repo,
    keyterms_from_catalogue,
    meeting_slug,
    resolve_term,
)
from kyun.kt.transcript import load_transcript
from kyun.llm import LLM, FakeLLM

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "kt" / "listmonk-kt-sample.json"
TERMS = [
    "app.concurrency", "app.message_rate", "app.batch_size", "app.max_send_errors", "config.toml", "queries.sql",
    "internal/manager/manager.go", "manager.go", "cmd/campaigns.go", "github.com/lib/pq", "lib/pq",
    "github.com/labstack/echo/v4", "internal/manager", "app concurrency",
]


def _by(decisions, subject, predicate):
    return [d for d in decisions if d.subject.lower() == subject.lower() and d.predicate == predicate]


# ---------- heuristics ----------


def test_heuristic_extraction_finds_the_concurrency_decision_with_its_evidence():
    t = load_transcript(SAMPLE)
    decisions = extract_heuristic(t.utterances, terms=TERMS, speakers=t.speakers)
    conc = _by(decisions, "app.concurrency", "config_value")
    assert len(conc) == 1
    d = conc[0]
    assert d.object == "10" and d.utterance_seqs == [3] and d.speaker_label == "S1"
    assert d.rationale and "SES" in d.rationale and "rate limit" in d.rationale
    assert d.confidence == 0.5 and d.about_terms == ["app.concurrency"]
    assert not any(x.object == "25" for x in decisions), "the historical value must not become a decision"
    assert [x.predicate for x in _by(decisions, "app.concurrency", "constraint")] == ["constraint"]  # "10 से ऊपर मत बढ़ाना"


def test_heuristic_extraction_covers_values_owners_choices_and_constraints():
    t = load_transcript(SAMPLE)
    decisions = extract_heuristic(t.utterances, terms=TERMS, speakers=t.speakers)
    got = {(d.subject, d.predicate): d for d in decisions}
    assert got[("message_rate", "config_value")].object == "10"
    assert got[("app.batch_size", "config_value")].object == "1000" and "Postgres" in got[("app.batch_size", "config_value")].rationale
    mse = got[("max_send_errors", "config_value")]
    assert mse.object == "1000" and mse.utterance_seqs == [11] and "SMTP" in mse.rationale
    assert got[("max_msg_retries", "config_value")].object == "2"
    assert got[("internal/manager", "owner")].object == "Priya Nair" and got[("internal/manager", "owner")].utterance_seqs == [27]
    assert got[("cmd/campaigns.go", "owner")].object == "Priya Nair"
    q = got[("queries.sql", "chose")]
    assert "query plans" in (q.rationale or "") and q.utterance_seqs == [21]
    assert ("manager.go", "constraint") in got and ("docker-compose.yml", "constraint") in got
    assert ("github.com/lib/pq", "chose") in got
    assert ("config.toml", "kt_said") not in got, "a bare 'kyunki' is not a decision"
    assert all(0 <= d.utterance_seqs[0] < 40 for d in decisions)


def test_extract_decisions_uses_heuristics_with_the_fake_llm():
    t = load_transcript(SAMPLE)
    out = extract_decisions(t.utterances, keyterms=["app.concurrency"], terms=TERMS, llm=FakeLLM(), speakers=t.speakers)
    assert out.signal == "heuristic_kt" and out.llm_used is False and out.backend == "fake"
    assert any(d.subject == "app.concurrency" and d.object == "10" for d in out.decisions)


class _StubLLM(LLM):
    backend, model = "stub", "stub-1"

    def __init__(self, reply: str):
        self.reply, self.prompts = reply, []

    def complete(self, system, user, *, temperature=0.1, max_tokens=1024):
        self.prompts.append(user)
        return self.reply


def test_llm_extraction_validates_strict_json_and_drops_unanchored_rows():
    t = load_transcript(SAMPLE)
    reply = """```json
{"decisions": [
  {"subject": "app.concurrency", "predicate": "config_value", "object": "10", "rationale": "SES throttling", "speaker_label": "S1", "utterance_seqs": [3, 7], "about_terms": ["app.concurrency"], "confidence": 0.95},
  {"subject": "internal/manager", "predicate": "owner", "object": "Priya Nair", "utterance_seqs": [27], "confidence": 0.2},
  {"subject": "ghost", "predicate": "chose", "object": "x", "utterance_seqs": [999]},
  {"subject": "", "predicate": "chose", "object": "x", "utterance_seqs": [1]},
  {"subject": "bad", "predicate": "not_a_predicate", "object": "x", "utterance_seqs": [1]}
]}
```"""
    llm = _StubLLM(reply)
    # the last row has an invalid predicate: pydantic rejects the whole window, so nothing comes back from the model
    decisions, errors = extract_with_llm(llm, t.utterances, keyterms=["app.concurrency"], speakers=t.speakers)
    assert decisions == [] and errors and "ValidationError" in errors[0]
    good = reply.replace(',\n  {"subject": "bad", "predicate": "not_a_predicate", "object": "x", "utterance_seqs": [1]}', "")
    llm = _StubLLM(good)
    decisions, errors = extract_with_llm(llm, t.utterances, keyterms=["app.concurrency"], speakers=t.speakers)
    assert errors == []
    assert [(d.subject, d.predicate, d.object, d.utterance_seqs, d.confidence) for d in decisions] == [
        ("app.concurrency", "config_value", "10", [3, 7], 0.8),
        ("internal/manager", "owner", "Priya Nair", [27], 0.5),
    ]
    assert decisions[1].speaker_label == "S1"
    assert "[3] S1 (00:28): हमने app.concurrency" in llm.prompts[0] and "KEYTERMS: app.concurrency" in llm.prompts[0]
    out = extract_decisions(t.utterances, llm=llm, terms=TERMS, speakers=t.speakers)
    assert out.signal == "llm_kt" and out.llm_used and out.backend == "stub" and len(out.decisions) == 2


def test_llm_garbage_falls_back_to_heuristics_with_errors_recorded():
    t = load_transcript(SAMPLE)
    out = extract_decisions(t.utterances, llm=_StubLLM("sorry, no json here"), terms=TERMS, speakers=t.speakers)
    assert out.signal == "heuristic_kt" and out.llm_used is False and out.errors
    assert any(d.subject == "app.concurrency" and d.object == "10" for d in out.decisions)


# ---------- entities ----------


def test_aliases_pass_the_precision_guard():
    assert guard_ok("app.concurrency") and guard_ok("message_rate") and guard_ok("internal/manager") and guard_ok("NewManager")
    assert not guard_ok("concurrency") and not guard_ok("Run") and not guard_ok("pq")
    assert build_aliases("ConfigKey", "app.concurrency", "config.toml", "app.concurrency") == ("app.concurrency", "app concurrency")
    assert build_aliases("ConfigKey", "app.message_rate", "config.toml", "app.message_rate") == ("app.message_rate", "message_rate", "app message rate")
    assert build_aliases("File", "manager.go", "internal/manager/manager.go", None) == ("internal/manager/manager.go", "manager.go")
    assert build_aliases("Symbol", "Run", "cmd/main.go", None) == ()
    assert build_aliases("Symbol", "NewManager", "internal/manager/manager.go", None) == ("NewManager", "new manager")
    assert build_aliases("Dependency", "github.com/lib/pq", None, None) == ("github.com/lib/pq", "lib/pq", "lib pq")
    assert build_aliases("Dependency", "github.com/labstack/echo/v4", None, None) == ("github.com/labstack/echo/v4", "labstack/echo/v4", "echo/v4", "echo v4")
    assert build_aliases("Module", "manager", "internal/manager", None) == ("internal/manager",)


def _catalogue():
    rows = [
        {"id": "cfg:r:config.toml::app.concurrency", "label": "ConfigKey", "name": "app.concurrency", "path": "config.toml", "key": "app.concurrency", "tokens": "app concurrency"},
        {"id": "file:r:internal/manager/manager.go", "label": "File", "name": "manager.go", "path": "internal/manager/manager.go", "key": None, "tokens": "internal manager go"},
        {"id": "module:r:internal/manager", "label": "Module", "name": "manager", "path": "internal/manager", "key": None, "tokens": "internal manager"},
        {"id": "dep:r:go:github.com/lib/pq", "label": "Dependency", "name": "github.com/lib/pq", "path": None, "key": None, "tokens": "github com lib pq"},
        {"id": "sym:r:internal/manager/manager.go::NewManager", "label": "Symbol", "name": "NewManager", "path": "internal/manager/manager.go", "key": None, "tokens": "new manager"},
    ]
    return [EntityRef.from_row(r) for r in rows]


def test_matcher_matches_whole_tokens_prefers_longest_and_hears_spoken_forms():
    m = Matcher(_catalogue())
    found = m.find("humne app.concurrency ko 10 pe rakha, internal/manager/manager.go dekho aur lib/pq hi driver hai")
    assert [(e.label, alias) for e, alias in found] == [("ConfigKey", "app.concurrency"), ("File", "internal/manager/manager.go"), ("Dependency", "lib/pq")]
    assert m.find("app.concurrency_limit badha do") == []
    assert m.find("app.concurrencyको") == []
    assert [(e.label, a) for e, a in m.find("app concurrency ko dus pe rakha")] == [("ConfigKey", "app concurrency")]
    assert [(e.label, a) for e, a in m.find("manager.go me NewManager hai")] == [("File", "manager.go"), ("Symbol", "NewManager")]
    assert [e.label for e, _ in m.find("internal/manager ka owner Priya hai")] == ["Module"]
    assert m.find("internal/manager ka owner Priya hai", labels=("File", "ConfigKey")) == []


def test_resolve_term_without_graph_uses_exact_and_spoken_aliases_only():
    m = Matcher(_catalogue())
    assert resolve_term("app.concurrency", m).id == "cfg:r:config.toml::app.concurrency"
    assert resolve_term("App Concurrency", m).label == "ConfigKey"
    assert resolve_term("manager.go", m).canonical == "internal/manager/manager.go"
    assert resolve_term("lib pq", m).canonical == "github.com/lib/pq"
    assert resolve_term("concurrency", m) is None and resolve_term("", m) is None
    assert resolve_term("internal/manager", m, labels=("File",)) is None


def test_keyterms_prefer_spoken_forms_and_sentences_and_slugs_are_stable():
    assert keyterms_from_catalogue(_catalogue()) == ["app.concurrency", "manager.go", "manager", "lib/pq", "NewManager"]
    assert decision_sentence("config.toml::app.concurrency", "config_value", "10", "Rohan Mehta", "KT") == 'config.toml::app.concurrency is 10 (said by Rohan Mehta in KT "KT")'
    assert decision_sentence("internal/manager", "owner", "Priya Nair", "Rohan", "KT").startswith("internal/manager is owned by Priya Nair")
    assert meeting_slug("Listmonk handover: campaign manager & config", 1_792_470_600_000, "x") == "listmonk-handover-campaign-manager-config-20261020"
    assert meeting_slug("Same title", None, "first words") == meeting_slug("Same title", None, "first words")
    assert meeting_slug("Same title", None, "first words") != meeting_slug("Same title", None, "other words")


def test_kt_cli_registers_the_contract_flags():
    from kyun.kt.cli import register

    parser = argparse.ArgumentParser()
    register(parser.add_subparsers(dest="command"))
    args = parser.parse_args(["kt", "ingest", "--repo", "knadh/listmonk", "--transcript", "f.json", "--title", "T", "--speakers", "3", "--language", "hi-IN", "--no-translate"])
    assert (args.repo, args.transcript, args.audio, args.title, args.speakers, args.language, args.no_translate) == ("knadh/listmonk", "f.json", None, "T", 3, "hi-IN", True)
    with pytest.raises(SystemExit):
        parser.parse_args(["kt", "ingest", "--repo", "r", "--audio", "a.wav", "--transcript", "t.json"])
    with pytest.raises(SystemExit):
        parser.parse_args(["kt", "ingest", "--repo", "r"])
    assert parser.parse_args(["kt", "list", "--repo", "r"]).kt_command == "list"


# ---------- end to end on Neo4j ----------



@pytest.fixture
def kt_people(graph):
    """People are shared across repositories (the sample's speakers also speak in the real listmonk call), so these
    tests never delete a Person by id: `wipe_repo` (run by `test_repo`) removes the test's speaker identities and only
    the people nothing else refers to any more."""
    yield


def _seed(graph, repo: str) -> None:
    now = int(time.time() * 1000)
    graph.query(
        """
        MERGE (r:Repo {id: $rid}) SET r.full_name = $repo
        MERGE (cfg:File {id: $cfg_file}) SET cfg.repo = $repo, cfg.path = 'config.toml', cfg.name = 'config.toml', cfg.ext = 'toml',
              cfg.tokens = 'config toml', cfg.is_config = true, cfg.alive = true, cfg.touch_count = 5
        MERGE (k:ConfigKey {id: $k1}) SET k.repo = $repo, k.key = 'app.concurrency', k.path = 'config.toml', k.tokens = 'app concurrency', k.current_value = '10'
        MERGE (k)-[:SET_IN]->(cfg)
        MERGE (k2:ConfigKey {id: $k2}) SET k2.repo = $repo, k2.key = 'app.message_rate', k2.path = 'config.toml', k2.tokens = 'app message rate'
        MERGE (k2)-[:SET_IN]->(cfg)
        MERGE (mod:Module {id: $mod}) SET mod.repo = $repo, mod.path = 'internal/manager', mod.name = 'manager', mod.tokens = 'internal manager'
        MERGE (mg:File {id: $mg}) SET mg.repo = $repo, mg.path = 'internal/manager/manager.go', mg.name = 'manager.go', mg.ext = 'go',
              mg.tokens = 'internal manager go', mg.alive = true, mg.touch_count = 9
        MERGE (mg)-[:IN]->(mod)
        MERGE (cg:File {id: $cg}) SET cg.repo = $repo, cg.path = 'cmd/campaigns.go', cg.name = 'campaigns.go', cg.ext = 'go', cg.tokens = 'cmd campaigns go', cg.alive = true, cg.touch_count = 7
        MERGE (gm:File {id: $gm}) SET gm.repo = $repo, gm.path = 'go.mod', gm.name = 'go.mod', gm.ext = 'mod', gm.tokens = 'go mod', gm.alive = true, gm.touch_count = 3
        MERGE (d:Dependency {id: $dep}) SET d.repo = $repo, d.name = 'github.com/lib/pq', d.ecosystem = 'go', d.tokens = 'github com lib pq'
        MERGE (d)-[:DECLARED_IN]->(gm)
        MERGE (p:Person {id: 'person:gh:rohanm'}) SET p.name = 'Rohan M', p.login = 'rohanm', p.kind = 'contributor', p.tokens = 'rohan m'
        MERGE (i:Identity {id: $ident}) SET i.kind = 'email', i.value = 'rohan.mehta@example.com'
        MERGE (i)-[:IDENTITY_OF]->(p)
        """,
        {
            "rid": ids.repo_id(repo), "repo": repo, "cfg_file": ids.file_id(repo, "config.toml"),
            "k1": ids.config_key_id(repo, "config.toml", "app.concurrency"), "k2": ids.config_key_id(repo, "config.toml", "app.message_rate"),
            "mod": ids.module_id(repo, "internal/manager"), "mg": ids.file_id(repo, "internal/manager/manager.go"),
            "cg": ids.file_id(repo, "cmd/campaigns.go"), "gm": ids.file_id(repo, "go.mod"), "dep": ids.dependency_id(repo, "go", "github.com/lib/pq"),
            "ident": ids.identity_id("email", "rohan.mehta@example.com"),
        },
    )
    graph.run_named(
        "record_decision",
        {
            "rows": [
                {
                    "id": f"dec:{repo}:config_value:seed", "repo": repo, "kind": "config_value", "key": "config.toml::app.concurrency|config_value",
                    "subject": "config.toml::app.concurrency", "predicate": "config_value", "object": "10", "text": "app.concurrency is 10",
                    "rationale": None, "valid_from": 1_600_000_000_000, "confidence": 0.95, "signal": "config_diff", "created_at": now,
                }
            ],
            "now": now,
        },
        write=True,
    )
    graph.query("CALL db.awaitIndexes(60)")


@pytest.mark.neo4j
def test_ingest_kt_end_to_end_confirms_the_committed_value(graph, test_repo, kt_people):
    from kyun.kt import service

    _seed(graph, test_repo)
    assert "app.concurrency" in keyterms_for_repo(graph, test_repo)
    t = load_transcript(SAMPLE)
    result = ingest_kt(
        graph, test_repo, title=t.title, utterances=t.utterances, speakers=t.speakers, started_at=t.started_at, language=t.language,
        llm=FakeLLM(), source=t.source, summary=t.note,
    )
    mid = result["meeting_id"]
    assert mid == ids.meeting_id(test_repo, "listmonk-handover-campaign-manager-and-config-20261020")
    assert result["utterances"] == 40 and result["decision_signal"] == "heuristic_kt" and result["chunks"] == 40
    assert result["speakers"]["S1"] == "person:gh:rohanm", "the e-mail identity links the speaker to the known contributor"
    assert result["speakers"]["S2"] == ids.person_id(email="priya.nair@example.com")

    counts = graph.read(
        "MATCH (m:Meeting {id: $id}) OPTIONAL MATCH (m)-[:HAS]->(u:Utterance) WITH m, count(u) AS n "
        "OPTIONAL MATCH (m)-[:HAS]->(:Utterance)-[:NEXT]->(:Utterance) WITH m, n, count(*) AS nxt "
        "OPTIONAL MATCH (m)-[:ABOUT_REPO]->(r:Repo) RETURN n, nxt, r.full_name AS repo, m.language AS lang, m.duration_ms AS dur",
        {"id": mid},
    ).records[0]
    assert counts == {"n": 40, "nxt": 39, "repo": test_repo, "lang": "hi-IN", "dur": 412_000}
    assert graph.read("MATCH (:Utterance {meeting_id: $id})-[:SPOKEN_BY]->(p:Person) RETURN count(DISTINCT p) AS n", {"id": mid}).scalar() == 3
    assert graph.read("MATCH (i:Identity {kind: 'speaker'})-[:IDENTITY_OF]->() WHERE i.value STARTS WITH $id RETURN count(i) AS n", {"id": mid}).scalar() == 3
    assert graph.read("MATCH (p:Person {id: $pid}) RETURN p.kind AS k", {"pid": result["speakers"]["S2"]}).scalar() == "speaker"

    mentions = graph.read(
        "MATCH (u:Utterance {meeting_id: $id})-[m:MENTIONS]->(e) RETURN u.seq AS seq, head(labels(e)) AS label, coalesce(e.key, e.name) AS name, m.term AS term ORDER BY seq",
        {"id": mid},
    ).records
    assert {"seq": 3, "label": "ConfigKey", "name": "app.concurrency", "term": "app.concurrency"} in mentions
    assert any(m["seq"] == 19 and m["label"] == "File" and m["name"] == "manager.go" for m in mentions)
    assert any(m["seq"] == 23 and m["label"] == "Dependency" and m["name"] == "github.com/lib/pq" for m in mentions)
    assert not any(m["label"] == "Module" for m in mentions)

    rows = graph.read(
        """
        MATCH (d:Decision {repo: $repo}) WHERE d.key IN ['config.toml::app.concurrency|config_value', 'kt|config.toml::app.concurrency|config_value']
        OPTIONAL MATCH (d)-[:STATED_BY]->(p:Person)
        OPTIONAL MATCH (d)-[:EVIDENCED_BY]->(u:Utterance)
        OPTIONAL MATCH (d)-[:DECIDED_IN]->(m:Meeting)
        OPTIONAL MATCH (d)-[:ABOUT]->(a)
        RETURN d.kind AS kind, d.status AS status, d.object AS object, d.signal AS signal, d.confidence AS conf, d.rationale AS rationale,
               p.id AS person, collect(DISTINCT u.seq) AS seqs, m.id AS meeting, collect(DISTINCT a.id) AS about, d.valid_from AS vf
        ORDER BY vf
        """,
        {"repo": test_repo},
    ).records
    assert [r["kind"] for r in rows] == ["config_value", "kt"]
    assert [r["status"] for r in rows] == ["active", "active"], "same value from the call confirms, it does not supersede"
    kt = rows[1]
    assert kt["object"] == "10" and kt["signal"] == "heuristic_kt" and kt["conf"] == 0.5 and "SES" in kt["rationale"]
    assert kt["person"] == "person:gh:rohanm" and kt["seqs"] == [3] and kt["meeting"] == mid
    assert kt["about"] == [ids.config_key_id(test_repo, "config.toml", "app.concurrency")]
    assert graph.read("MATCH (:Decision {repo: $repo})-[s:SUPERSEDES]->() RETURN count(s) AS n", {"repo": test_repo}).scalar() == 0
    confirms = graph.read(
        "MATCH (k:Decision {repo: $repo, kind: 'kt'})-[:CONFIRMS]->(c:Decision) RETURN c.id AS c", {"repo": test_repo}
    ).records
    assert confirms == [{"c": f"dec:{test_repo}:config_value:seed"}], "the spoken value is linked to the code value it agrees with"

    owner = graph.read(
        "MATCH (d:Decision {repo: $repo, predicate: 'owner'})-[:ABOUT]->(a) RETURN d.subject AS s, d.object AS o, head(labels(a)) AS label ORDER BY s",
        {"repo": test_repo},
    ).records
    assert {"s": "internal/manager", "o": "Priya Nair", "label": "Module"} in owner
    assert {"s": "cmd/campaigns.go", "o": "Priya Nair", "label": "File"} in owner
    rate = graph.read("MATCH (d:Decision {repo: $repo, predicate: 'config_value'}) WHERE d.subject CONTAINS 'message_rate' RETURN d.key AS k, d.object AS o", {"repo": test_repo}).records
    assert rate == [{"k": "kt|config.toml::app.message_rate|config_value", "o": "10"}], "a bare key resolves to the known ConfigKey's canonical subject"
    assert graph.read("MATCH (c:Chunk {repo: $repo, source_kind: 'utterance'})-[:FROM]->(:Utterance) RETURN count(c) AS n", {"repo": test_repo}).scalar() == 40

    listed = service.meetings(test_repo, graph=graph)
    assert len(listed) == 1 and listed[0]["utterances"] == 40 and listed[0]["speakers"] == 3 and listed[0]["decisions"] == len(result["decisions"])
    assert listed[0]["started_at_iso"] == "2026-10-20T04:30:00Z"
    detail = service.meeting(mid, graph=graph)
    assert len(detail["utterances"]) == 40 and detail["utterances"][3]["speaker_name"] == "Rohan M"
    assert any(m["name"] == "app.concurrency" for m in detail["utterances"][3]["mentions"])
    assert {d["id"] for d in detail["decisions"]} == {d["id"] for d in result["decisions"]}
    kt_detail = next(d for d in detail["decisions"] if d["key"] == "kt|config.toml::app.concurrency|config_value")
    assert kt_detail["stated_by"]["id"] == "person:gh:rohanm" and kt_detail["evidence"] == [ids.utterance_id(mid, 3)]
    assert service.meeting("mtg:nope", graph=graph) is None

    again = ingest_kt(graph, test_repo, title=t.title, utterances=t.utterances, speakers=t.speakers, started_at=t.started_at, language=t.language, llm=FakeLLM())
    assert again["meeting_id"] == mid
    after = graph.read("MATCH (n {repo: $repo}) RETURN head(labels(n)) AS l, count(*) AS n", {"repo": test_repo}).records
    by_label = {r["l"]: r["n"] for r in after}
    assert by_label["Meeting"] == 1 and by_label["Utterance"] == 40 and by_label["Chunk"] == 40
    assert by_label["Decision"] == 1 + len(result["decisions"])


@pytest.mark.neo4j
def test_ingest_kt_different_value_contradicts_and_never_supersedes_code(graph, test_repo, kt_people):
    _seed(graph, test_repo)
    now = int(time.time() * 1000)
    rows = [{"speaker": "S1", "start_ms": 0, "end_ms": 6000, "text": "humne app.concurrency ko 20 pe rakha hai kyunki SES quota badh gaya."}]
    result = ingest_kt(graph, test_repo, title="Follow-up KT", utterances=rows, speakers={"S1": "Rohan Mehta"}, started_at=now, llm=FakeLLM())
    assert len(result["decisions"]) == 1
    d = result["decisions"][0]
    assert d["key"] == "kt|config.toml::app.concurrency|config_value" and d["object"] == "20" and d["status"] == "active"
    assert d["superseded"] == [] and d["rationale"] == "SES quota badh gaya"
    assert d["contradicts"] == [f"dec:{test_repo}:config_value:seed"]
    assert graph.read("MATCH (:Decision {repo: $repo})-[s:SUPERSEDES]->() RETURN count(s) AS n", {"repo": test_repo}).scalar() == 0
    code = graph.read("MATCH (d:Decision {id: $id}) RETURN d.status AS s, d.object AS o", {"id": f"dec:{test_repo}:config_value:seed"}).records
    assert code == [{"s": "active", "o": "10"}], "a handover call never overwrites what the repository records"

    # a later call that changes its mind supersedes the earlier spoken value, inside the KT key space only
    later = [{"speaker": "S1", "start_ms": 0, "end_ms": 6000, "text": "humne app.concurrency ko 30 pe rakha hai kyunki naya quota mila."}]
    second = ingest_kt(graph, test_repo, title="Second KT", utterances=later, speakers={"S1": "Rohan Mehta"}, started_at=now + 60_000, llm=FakeLLM())
    assert second["decisions"][0]["superseded"] == [d["id"]]


@pytest.mark.neo4j
def test_answer_keeps_the_repository_record_in_the_lead_and_names_the_conflict(graph, test_repo, kt_people):
    """A handover call that contradicts the repository must not win: the answer leads with the code record,
    cites the call, says the two conflict and loses confidence for it."""
    from kyun.answer.service import ask

    _seed(graph, test_repo)
    now = int(time.time() * 1000)
    rows = [{"speaker": "S1", "start_ms": 0, "end_ms": 6000, "text": "humne app.concurrency ko 20 pe rakha hai kyunki SES quota badh gaya."}]
    result = ingest_kt(graph, test_repo, title="Follow-up KT", utterances=rows, speakers={"S1": "Rohan Mehta"}, started_at=now, llm=FakeLLM())
    kt_id = result["decisions"][0]["id"]
    code_id = f"dec:{test_repo}:config_value:seed"

    r = ask("why is app.concurrency set the way it is?", test_repo, graph=graph, llm=FakeLLM())
    assert not r.refused
    assert r.evidence_chain[0].id == code_id, "the repository decision leads, not the spoken one"
    assert f"[{code_id}]" in r.answer and f"[{kt_id}]" in r.answer
    assert "conflict" in r.answer
    assert "a recorded handover call contradicts the repository record" in r.confidence.reasons
    assert any(step.id == kt_id for step in r.evidence_chain)


@pytest.mark.neo4j
def test_spoken_value_confirms_the_same_key_defined_in_another_file(graph, test_repo, kt_people):
    """A setting moved from config.toml into schema.sql: the call agrees with schema.sql, not with the removal."""
    _seed(graph, test_repo)
    now = int(time.time() * 1000)
    graph.query(
        "MERGE (f:File {id: $fid}) SET f.repo = $repo, f.path = 'schema.sql', f.name = 'schema.sql' "
        "MERGE (k:ConfigKey {id: $kid}) SET k.repo = $repo, k.key = 'app.concurrency', k.path = 'schema.sql' MERGE (k)-[:SET_IN]->(f)",
        {"repo": test_repo, "fid": ids.file_id(test_repo, "schema.sql"), "kid": ids.config_key_id(test_repo, "schema.sql", "app.concurrency")},
    )
    base = {"repo": test_repo, "kind": "config_value", "predicate": "config_value", "rationale": None, "confidence": 0.95, "signal": "config_diff", "created_at": now}
    graph.run_named("record_decision", {"rows": [
        {**base, "id": f"dec:{test_repo}:config_value:removed", "key": "config.toml::app.concurrency|config_value",
         "subject": "config.toml::app.concurrency", "object": "removed", "text": "app.concurrency was removed", "valid_from": 1_700_000_000_000},
    ], "now": now}, write=True)
    graph.run_named("record_decision", {"rows": [
        {**base, "id": f"dec:{test_repo}:config_value:schema", "key": "schema.sql::app.concurrency|config_value",
         "subject": "schema.sql::app.concurrency", "object": "10", "text": "app.concurrency in schema.sql is 10", "valid_from": 1_700_000_000_000},
    ], "now": now}, write=True)
    rows = [{"speaker": "S1", "start_ms": 0, "end_ms": 6000, "text": "humne app.concurrency ko 10 pe rakha hai kyunki SES throttle karta hai."}]
    result = ingest_kt(graph, test_repo, title="KT", utterances=rows, speakers={"S1": "Rohan Mehta"}, started_at=now, llm=FakeLLM())
    d = result["decisions"][0]
    assert d.get("confirms") == [f"dec:{test_repo}:config_value:schema"] and not d.get("contradicts")

    # re-running the call clears the old verdicts instead of stacking new ones on top
    again = ingest_kt(graph, test_repo, title="KT", utterances=rows, speakers={"S1": "Rohan Mehta"}, started_at=now, llm=FakeLLM())
    assert again["decisions"][0].get("confirms") == [f"dec:{test_repo}:config_value:schema"]
    n = graph.read("MATCH (:Decision {repo: $repo, kind: 'kt'})-[x:CONFIRMS|CONTRADICTS]->() RETURN count(x) AS n", {"repo": test_repo}).scalar()
    assert n == 1
