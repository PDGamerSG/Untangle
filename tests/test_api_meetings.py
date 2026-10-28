"""The meeting adapter shapes KT service rows into the web contract (web/src/lib/types.ts MeetingSummary/MeetingDetail)."""

from __future__ import annotations

from types import SimpleNamespace

from kyun.api import meetings as shape


def _row() -> dict:
    return {
        "id": "mtg:o/r:kt-1", "repo": "o/r", "title": "Handover", "started_at_iso": "2026-10-20T04:30:00Z", "duration_ms": 412_000,
        "language": "hi-IN", "source": "transcript-json", "audio_uri": None, "summary": None,
        "utterances": [
            {"id": "utt:mtg:o/r:kt-1#0000", "seq": 0, "speaker_label": "S1", "speaker_name": "Rohan M", "person_id": "person:gh:rohanm",
             "start_ms": 0, "end_ms": 4000, "text": "app.concurrency ko 10 pe rakha hai", "text_en": None, "language": "hi-IN",
             "mentions": [{"id": "cfg:o/r:config.toml::app.concurrency", "label": "ConfigKey", "name": "app.concurrency"}]},
            {"id": "utt:mtg:o/r:kt-1#0001", "seq": 1, "speaker_label": "S2", "speaker_name": None, "person_id": None,
             "start_ms": 4000, "end_ms": 7000, "text": "theek hai", "text_en": "okay", "language": "hi-IN", "mentions": []},
        ],
        "decisions": [{"id": "dec:o/r:kt:abc"}],
    }


def test_summary_counts_are_explicit():
    out = shape.summary_out({**_row(), "utterances": 40, "speakers": 3, "decisions": 15})
    assert (out["utterance_count"], out["speaker_count"], out["decision_count"]) == (40, 3, 15)
    assert out["started_at_iso"] == "2026-10-20T04:30:00Z"


def test_detail_builds_speaker_legend_and_full_cards(monkeypatch):
    card = SimpleNamespace(model_dump=lambda **_: {"id": "dec:o/r:kt:abc", "kind": "kt", "text": "app.concurrency is 10"})
    monkeypatch.setattr(shape.answer_service, "why_path", lambda did, graph=None: SimpleNamespace(decision=card))
    out = shape.detail_out(_row(), graph=None)
    assert out["speakers"] == [
        {"label": "S1", "person": {"id": "person:gh:rohanm", "name": "Rohan M"}},
        {"label": "S2", "person": None},
    ]
    assert out["utterances"][0]["speaker"] == {"id": "person:gh:rohanm", "name": "Rohan M"}
    assert out["utterances"][0]["meeting_id"] == "mtg:o/r:kt-1"
    assert out["utterances"][0]["mentions"][0]["name"] == "app.concurrency"
    assert out["decisions"] == [{"id": "dec:o/r:kt:abc", "kind": "kt", "text": "app.concurrency is 10"}]
    assert (out["utterance_count"], out["speaker_count"], out["decision_count"]) == (2, 2, 1)


def test_one_unreadable_decision_does_not_hide_the_meeting(monkeypatch):
    def boom(did, graph=None):
        raise LookupError(did)

    monkeypatch.setattr(shape.answer_service, "why_path", boom)
    out = shape.detail_out(_row(), graph=None)
    assert out["decisions"] == [] and len(out["utterances"]) == 2
