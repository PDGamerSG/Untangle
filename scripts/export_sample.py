"""Snapshot real answers from the live graph into web/sample/ so the web app's sample mode shows exactly what Kyun
produced, never hand-written stand-ins:

    uv run python scripts/export_sample.py --repo knadh/listmonk

Every fixture is the JSON the API returns for the same request (asked with mode "both", so the vector-only baseline
in the side-by-side is the real baseline). Re-run after re-ingesting.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kyun.answer import service
from kyun.api.meetings import detail_out, summary_out
from kyun.config import PROJECT_ROOT
from kyun.kt import service as kt_service

OUT = PROJECT_ROOT / "web" / "sample"

QUESTIONS = {
    "concurrency": ("why is app.concurrency set the way it is?", None),
    "concurrency-asof": ("why is app.concurrency set the way it is?", "2020-01-01"),
    "still-use": ("do we still use github.com/lib/pq?", None),
    "who": ("who should I ask about internal/manager?", None),
    "changed": ("what changed in docker-compose.yml?", None),
    "refusal": ("why does listmonk use MongoDB?", None),
}


def dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def as_json(model: Any) -> Any:
    return model.model_dump(mode="json", by_alias=True) if hasattr(model, "model_dump") else model


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default="knadh/listmonk")
    args = parser.parse_args(argv)
    graph = service.get_graph()

    dump(OUT / "health.json", service.health(graph=graph))
    dump(OUT / "repos.json", [as_json(r) for r in service.repos(graph=graph) if r.full_name == args.repo])

    decision_ids: list[str] = []
    for name, (question, at) in QUESTIONS.items():
        r = as_json(service.ask(question, args.repo, at=at, mode="both", graph=graph))
        dump(OUT / "ask" / f"{name}.json", r)
        decision_ids += [c for c in r["citations"] if c.startswith("dec:")]
        decision_ids += [s["id"] for s in r["evidence_chain"] if (s.get("id") or "").startswith("dec:")]
        decision_ids += [x for s in r["supersession"] for x in (s["newer"], s["older"])]
        print(f"ask/{name}.json  refused={r['refused']} confidence={r['confidence']['score']}")

    meetings = kt_service.meetings(args.repo, graph=graph)
    dump(OUT / "meetings.json", [summary_out(m) for m in meetings])
    meeting = None
    if meetings:
        raw = kt_service.meeting(meetings[0]["id"], graph=graph)
        meeting = detail_out(raw, graph=graph) if raw else None
        if meeting:
            decision_ids += [d["id"] for d in meeting["decisions"]]
    dump(OUT / "meeting.json", meeting or {})

    cards: dict[str, Any] = {}
    paths: dict[str, Any] = {}
    queue = list(dict.fromkeys(decision_ids))
    while queue and len(cards) < 200:
        did = queue.pop(0)
        if did in cards:
            continue
        try:
            wp = as_json(service.why_path(did, graph=graph))
        except Exception as exc:  # noqa: BLE001
            print(f"skip {did}: {exc}")
            continue
        cards[did] = wp["decision"]
        queue += [d["id"] for d in wp["older"] + wp["newer"] if d["id"] not in cards]  # every version gets its own page
        paths[did] = {
            "evidence": wp["evidence"], "older": [d["id"] for d in wp["older"]], "newer": [d["id"] for d in wp["newer"]],
            "motivated_by": wp["motivated_by"], "implemented_by": wp["implemented_by"], "cypher": wp["cypher"],
        }
    dump(OUT / "decisions.json", {"exported_at": datetime.now(tz=UTC).isoformat(), "repo": args.repo, "cards": cards, "paths": paths})
    print(f"{len(cards)} decision cards, {len(paths)} why-paths, {len(meetings)} meetings -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
