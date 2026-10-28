"""Shape `kyun.kt.service` reads into the web contract (`MeetingSummary`, `MeetingDetail` in web/src/lib/types.ts).

The KT service returns graph-shaped rows (counts named after what they count, speakers as people, decisions as
compact maps); the web app wants explicit `*_count` fields, a speaker legend keyed by label, and full
`DecisionCard`s. Decision cards come from `kyun.answer.service.why_path`, the same projection the decision pages
use, so a decision reads identically wherever it appears."""

from __future__ import annotations

import logging
from typing import Any

from kyun.answer import service as answer_service
from kyun.graph.db import Graph

log = logging.getLogger("kyun.api.meetings")


def summary_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "repo": row.get("repo"),
        "title": row.get("title"),
        "started_at_iso": row.get("started_at_iso"),
        "duration_ms": row.get("duration_ms") or 0,
        "language": row.get("language"),
        "source": row.get("source"),
        "audio_uri": row.get("audio_uri"),
        "summary": row.get("summary"),
        "utterance_count": int(row.get("utterances") or 0),
        "speaker_count": int(row.get("speakers") or 0),
        "decision_count": int(row.get("decisions") or 0),
    }


def detail_out(row: dict[str, Any], *, graph: Graph) -> dict[str, Any]:
    utterances_in = row.get("utterances") or []
    speakers: dict[str, dict[str, Any]] = {}
    utterances: list[dict[str, Any]] = []
    for u in utterances_in:
        person = {"id": u["person_id"], "name": u.get("speaker_name") or u.get("speaker_label")} if u.get("person_id") else None
        label = u.get("speaker_label") or "speaker"
        speakers.setdefault(label, {"label": label, "person": person})
        utterances.append(
            {
                "id": u["id"], "meeting_id": row["id"], "seq": u.get("seq"), "text": u.get("text") or "",
                "text_en": u.get("text_en"), "start_ms": u.get("start_ms") or 0, "end_ms": u.get("end_ms") or 0,
                "speaker_label": label, "speaker": person, "language": u.get("language") or row.get("language"),
                "mentions": [{"id": m["id"], "label": m.get("label"), "name": m.get("name")} for m in u.get("mentions") or []],
            }
        )
    decisions: list[dict[str, Any]] = []
    for d in row.get("decisions") or []:
        try:
            decisions.append(answer_service.why_path(d["id"], graph=graph).decision.model_dump(mode="json", by_alias=True))
        except Exception as exc:  # noqa: BLE001 - one unreadable decision must not hide the meeting
            log.warning("decision %s could not be projected: %s", d.get("id"), exc)
    out = summary_out({**row, "utterances": len(utterances), "speakers": len(speakers), "decisions": len(decisions)})
    out.update({"utterances": utterances, "decisions": decisions, "speakers": list(speakers.values())})
    return out
