"""Transcript normalisation: the three inputs, merging, Devanagari-aware sentence splitting, coercion."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from untangle.kt.transcript import (
    MAX_UTTERANCE_CHARS,
    from_sarvam,
    from_text,
    from_untangle_json,
    load_transcript,
    normalise,
    parse_started_at,
    split_sentences,
)

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "kt" / "listmonk-kt-sample.json"


def test_sample_untangle_json_loads_40_ordered_utterances_with_speakers():
    t = load_transcript(SAMPLE)
    assert t.title == "Listmonk handover: campaign manager and config"
    assert t.language == "hi-IN" and t.source == "transcript-json"
    assert t.note and t.note.startswith("SYNTHETIC")
    assert len(t.utterances) == 40
    assert [u.seq for u in t.utterances] == list(range(40))
    assert t.utterances[3].speaker_label == "S1" and "app.concurrency" in t.utterances[3].text
    assert t.speakers["S1"]["name"] == "Rohan Mehta" and t.speakers["S1"]["email"] == "rohan.mehta@example.com"
    assert sorted(t.labels) == ["S1", "S2", "S3"]
    assert t.started_at == int(datetime(2026, 10, 20, 4, 30, tzinfo=UTC).timestamp() * 1000)
    assert t.duration_ms == 412_000
    assert all(u.language == "hi-IN" for u in t.utterances)
    assert all(a.end_ms <= b.start_ms for a, b in zip(t.utterances, t.utterances[1:], strict=False))


def test_sarvam_entries_merge_same_speaker_runs_closer_than_1_5s_only():
    doc = {
        "language_code": "hi-IN",
        "diarized_transcript": {
            "entries": [
                {"transcript": "pehla hissa", "start_time_seconds": 0.0, "end_time_seconds": 1.0, "speaker_id": "SPEAKER_00"},
                {"transcript": "doosra hissa", "start_time_seconds": 1.8, "end_time_seconds": 3.0, "speaker_id": "SPEAKER_00"},  # 0.8 s gap: merge
                {"transcript": "haan", "start_time_seconds": 3.2, "end_time_seconds": 4.0, "speaker_id": "SPEAKER_01"},
                {"transcript": "teesra hissa", "start_time_seconds": 4.1, "end_time_seconds": 5.0, "speaker_id": "SPEAKER_00"},  # other speaker between: no merge
                {"transcript": "chautha hissa", "start_time_seconds": 6.6, "end_time_seconds": 7.0, "speaker_id": "SPEAKER_00"},  # 1.6 s gap: no merge
            ]
        },
    }
    t = from_sarvam(doc, source="sarvam-rest")
    texts = [(u.speaker_label, u.text, u.start_ms, u.end_ms) for u in t.utterances]
    assert texts == [
        ("SPEAKER_00", "pehla hissa doosra hissa", 0, 3000),
        ("SPEAKER_01", "haan", 3200, 4000),
        ("SPEAKER_00", "teesra hissa", 4100, 5000),
        ("SPEAKER_00", "chautha hissa", 6600, 7000),
    ]
    assert t.language == "hi-IN" and t.source == "sarvam-rest"
    assert set(t.speakers) == {"SPEAKER_00", "SPEAKER_01"}


def test_long_entry_is_split_at_sentence_ends_including_the_danda():
    sentence_hi = "हमने app.concurrency को 10 पे रखा है क्योंकि SES का rate limit hit हो रहा था और campaign अटक जाती थी।"
    sentence_q = "क्या message_rate को भी साथ में बदलना चाहिए या वो अलग से tune होता है?"
    sentence_en = "The batch size stays at 1000 because the subscriber query is paginated in the manager."
    text = " ".join([sentence_hi, sentence_q, sentence_en] * 3)
    assert len(text) > MAX_UTTERANCE_CHARS
    rows = normalise([{"speaker": "S1", "start_ms": 0, "end_ms": 90_000, "text": text}])
    assert len(rows) >= 3
    assert all(len(u.text) <= MAX_UTTERANCE_CHARS for u in rows)
    assert all(u.text[-1] in ".?।" for u in rows), "pieces end at sentence boundaries"
    assert rows[0].text.startswith("हमने app.concurrency")
    assert " ".join(u.text for u in rows) == text
    assert rows[0].start_ms == 0 and rows[-1].end_ms == 90_000
    assert all(a.end_ms == b.start_ms for a, b in zip(rows, rows[1:], strict=False))
    assert [u.seq for u in rows] == list(range(len(rows)))


def test_split_sentences_glues_short_fragments_and_handles_danda():
    parts = split_sentences("हाँ। ठीक है। यह एक लंबा वाक्य है जो पच्चीस अक्षरों से ज़्यादा लंबा है। Dusra lamba sentence yahan par hai. Ok?")
    assert parts == ["हाँ। ठीक है। यह एक लंबा वाक्य है जो पच्चीस अक्षरों से ज़्यादा लंबा है।", "Dusra lamba sentence yahan par hai. Ok?"]
    assert split_sentences("app.concurrency ko 10 pe rakha hai.") == ["app.concurrency ko 10 pe rakha hai."]


def test_plain_text_transcript_with_timestamps_continuations_and_estimates():
    text = """
[00:05] Rohan: config.toml ke app section se shuru karte hain.
kyunki wahin se sawaal aate hain.
[00:12] Priya: theek hai, main notes bana rahi hoon.
Rohan: humne app.concurrency ko 10 pe rakha hai.
https://example.com/not-a-speaker-line
Priya: samajh gayi.
"""
    t = from_text(text, title="Short KT")
    assert t.source == "transcript-text" and t.title == "Short KT"
    assert t.speakers == {"S1": {"name": "Rohan", "login": None, "email": None}, "S2": {"name": "Priya", "login": None, "email": None}}
    u = t.utterances
    assert [x.speaker_label for x in u] == ["S1", "S2", "S1", "S2"]
    assert u[0].text == "config.toml ke app section se shuru karte hain. kyunki wahin se sawaal aate hain."
    assert u[0].start_ms == 5000 and u[1].start_ms == 12000
    assert u[0].end_ms <= u[1].start_ms
    assert u[2].start_ms >= u[1].end_ms and u[3].start_ms > u[2].start_ms  # estimated from text length, monotonic
    assert "https://example.com" in u[2].text  # a URL line continues the previous speaker


def test_sarvam_timestamps_only_response_gets_one_speaker_and_no_language():
    doc = {"transcript": "a. b.", "timestamps": {"words": ["a.", "b."], "start_time_seconds": [0.0, 2.0], "end_time_seconds": [1.0, 3.0]}}
    t = from_sarvam(doc)
    assert [u.speaker_label for u in t.utterances] == ["SPEAKER_00"]  # 1 s apart: merged into one turn
    assert t.utterances[0].text == "a. b." and t.language is None


def test_load_transcript_detects_the_three_formats(tmp_path):
    untangle = tmp_path / "k.json"
    untangle.write_text(json.dumps({"title": "K", "utterances": [{"speaker": "A", "start_ms": 0, "end_ms": 1000, "text": "namaste"}]}), encoding="utf-8")
    sarvam = tmp_path / "s.json"
    sarvam.write_text(json.dumps({"transcript": "namaste", "language_code": "hi-IN"}), encoding="utf-8")
    sarvam_list = tmp_path / "list.json"
    sarvam_list.write_text(json.dumps([{"transcript": "ek"}, {"transcript": "do"}]), encoding="utf-8")
    txt = tmp_path / "t.txt"
    txt.write_text("Rohan: namaste\nPriya: namaste", encoding="utf-8")
    assert load_transcript(untangle).source == "transcript-json" and load_transcript(untangle).title == "K"
    s = load_transcript(sarvam, language="hi-IN")
    assert s.source == "sarvam-batch" and s.utterances[0].text == "namaste" and s.title == "s"
    assert len(load_transcript(sarvam_list).utterances) == 1  # same placeholder speaker, 0 s apart: merged
    assert load_transcript(txt).source == "transcript-text"


def test_parse_started_at_variants():
    assert parse_started_at("2026-10-20T10:00:00+05:30") == int(datetime(2026, 10, 20, 4, 30, tzinfo=UTC).timestamp() * 1000)
    assert parse_started_at("2026-10-20T04:30:00Z") == parse_started_at("2026-10-20T04:30:00")  # naive = UTC
    assert parse_started_at(1_792_470_600) == 1_792_470_600_000
    assert parse_started_at(1_792_470_600_000) == 1_792_470_600_000
    assert parse_started_at("1792470600") == 1_792_470_600_000
    assert parse_started_at("not a date") is None and parse_started_at(None) is None and parse_started_at("") is None


def test_untrusted_rows_are_coerced_and_empty_ones_dropped():
    rows = normalise(
        [
            {"speaker": " Speaker One ", "start_ms": "abc", "end_ms": -5, "text": "  ok\x00 text\x07 here  "},
            {"speaker": "S2", "start_ms": 5000, "end_ms": 4000, "text": "   "},
            {"speaker_id": "SPEAKER_01", "start_ms": 9000.6, "end_ms": 9500, "text": "देवनागरी"},
        ]
    )
    assert [(u.speaker_label, u.start_ms, u.end_ms, u.text, u.language) for u in rows] == [
        ("Speaker_One", 0, 0, "ok text here", None),
        ("SPEAKER_01", 9001, 9500, "देवनागरी", "hi-IN"),
    ]
    t = from_untangle_json({"utterances": [{"speaker": "S1", "text": "x"}], "speakers": {"S1": "Rohan"}})
    assert t.speakers == {"S1": {"name": "Rohan", "login": None, "email": None}} and t.started_at is None
