"""`kyun kt ...` subcommands. The CLI owner imports `register(subparsers)`; the parser sets `func` so the
dispatcher can call `args.func(args)`. `python -m kyun.kt.cli` runs it standalone.

    kyun kt ingest --repo owner/name (--audio file.mp3 | --transcript file.json) [--title "..."] [--speakers 3]
                   [--language hi-IN] [--no-translate] [--json]
    kyun kt list --repo owner/name
    kyun kt show <meeting-id>"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from kyun.kt import service
from kyun.kt.sarvam import SarvamError

log = logging.getLogger("kyun.kt.cli")


def _emit(obj: Any) -> None:
    text = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    try:
        print(text)
    except UnicodeEncodeError:  # Windows consoles without UTF-8: escape instead of crashing
        print(json.dumps(obj, ensure_ascii=True, indent=2, default=str))


def _say(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "backslashreplace").decode("ascii"))


def run_ingest(args: argparse.Namespace) -> int:
    try:
        if args.audio:
            result = service.ingest_audio(
                args.repo, args.title or Path(args.audio).stem, args.audio, language=args.language, num_speakers=args.speakers,
                translate=not args.no_translate,
            )
        else:
            result = service.ingest_transcript(args.repo, args.transcript, title=args.title, language=args.language, translate=not args.no_translate)
    except (SarvamError, ValueError, FileNotFoundError) as exc:
        _say(f"kt ingest failed: {exc}")
        return 2
    if args.json:
        _emit(result)
        return 0
    _say(f"meeting {result['meeting_id']}  ({result['source']}, language {result.get('language') or 'unknown'})")
    _say(f"  utterances: {result['utterances']}   speakers: {len(result['speakers'])}   mentions: {result['mentions']}   translated: {result['translated']}   chunks: {result['chunks']}")
    _say(f"  decisions: {len(result['decisions'])} via {result['decision_signal']} (llm {result['llm']['backend']}/{result['llm']['model']})")
    for d in result["decisions"]:
        status = d.get("status", "active")
        notes = []
        if d.get("superseded"):
            notes.append(f"updates earlier call: {', '.join(d['superseded'])}")
        if d.get("confirms"):
            notes.append(f"confirms repo: {', '.join(d['confirms'])}")
        if d.get("contradicts"):
            notes.append(f"CONTRADICTS repo: {', '.join(d['contradicts'])}")
        _say(f"    [{status}] {d['text']}" + (f"  ({'; '.join(notes)})" if notes else ""))
    return 0


def run_list(args: argparse.Namespace) -> int:
    rows = service.meetings(args.repo)
    if args.json:
        _emit(rows)
        return 0
    if not rows:
        _say(f"no meetings for {args.repo}")
        return 0
    for m in rows:
        _say(f"{m['id']}  {m.get('started_at_iso') or '-'}  {m['title']}  ({m['utterances']} utterances, {m['speakers']} speakers, {m['decisions']} decisions)")
    return 0


def run_show(args: argparse.Namespace) -> int:
    m = service.meeting(args.id)
    if m is None:
        _say(f"no meeting {args.id}")
        return 1
    if args.json:
        _emit(m)
        return 0
    _say(f"{m['title']}  ({m.get('started_at_iso') or '-'}, {m.get('language') or 'unknown'}, {m.get('source')})")
    for u in m.get("utterances") or []:
        who = u.get("speaker_name") or u.get("speaker_label")
        _say(f"  [{u['seq']:>3}] {u['start_ms'] // 60000:02d}:{(u['start_ms'] // 1000) % 60:02d} {who}: {u['text']}")
        if u.get("text_en"):
            _say(f"        en: {u['text_en']}")
    for d in m.get("decisions") or []:
        _say(f"  decision [{d['status']}] {d['text']}")
    return 0


def run(args: argparse.Namespace) -> int:
    handlers = {"ingest": run_ingest, "list": run_list, "show": run_show}
    return handlers[args.kt_command](args)


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = subparsers.add_parser("kt", help="handover (KT) calls: transcribe with Sarvam and load into the graph")
    sub = p.add_subparsers(dest="kt_command", required=True)

    ing = sub.add_parser("ingest", help="transcribe an audio file (Sarvam) or load a transcript, then extract decisions")
    ing.add_argument("--repo", required=True, help="owner/name the call is about")
    src = ing.add_mutually_exclusive_group(required=True)
    src.add_argument("--audio", help="recording (wav/mp3/m4a/...): <= 30 s WAV uses the REST endpoint, longer files the batch job")
    src.add_argument("--transcript", help="Kyun transcript JSON, Sarvam response JSON, or 'Speaker: text' lines")
    ing.add_argument("--title", help="meeting title (defaults to the transcript's title or the file name)")
    ing.add_argument("--speakers", type=int, help="number of speakers, when known (helps diarisation)")
    ing.add_argument("--language", help="BCP-47 code such as hi-IN or en-IN; omit to auto-detect")
    ing.add_argument("--no-translate", action="store_true", help="skip the English rendering (text_en) even when SARVAM_API_KEY is set")
    ing.add_argument("--json", action="store_true", help="print the ingestion summary as JSON")
    ing.set_defaults(func=run_ingest)

    ls = sub.add_parser("list", help="list the meetings of a repository")
    ls.add_argument("--repo", required=True)
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(func=run_list)

    sh = sub.add_parser("show", help="print one meeting with its utterances and decisions")
    sh.add_argument("id", help="meeting id (mtg:owner/name:slug)")
    sh.add_argument("--json", action="store_true")
    sh.set_defaults(func=run_show)

    p.set_defaults(func=run)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="kyun")
    register(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
