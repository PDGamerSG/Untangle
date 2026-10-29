"""`untangle` command line (CONTRACTS §5): schema, ask, stats, serve here; `ingest`, `kt` and `eval` are registered by
their own packages through `register(subparsers)` when they are installed. The only module allowed to print."""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
from typing import Any

from untangle import __version__

log = logging.getLogger("untangle.cli")

_PLUGINS = ("untangle.ingest.cli", "untangle.kt.cli", "untangle.eval.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="untangle", description="Untangle: why is the code like this?")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="-v for INFO, -vv for DEBUG")
    parser.add_argument("--version", action="version", version=f"untangle {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    p = sub.add_parser("schema", help="ensure constraints and indexes")
    p.set_defaults(func=cmd_schema)

    p = sub.add_parser("ask", help='ask a question: untangle ask "why is the retry limit 3?" --repo owner/name')
    p.add_argument("question")
    p.add_argument("--repo", required=True, help="owner/name of an ingested repository")
    p.add_argument("--at", help="answer as of this date (YYYY-MM-DD)")
    p.add_argument("--baseline", action="store_true", help="also run the vector-only baseline (mode=both)")
    p.add_argument("--baseline-only", action="store_true", help="run only the vector-only baseline")
    p.add_argument("--json", action="store_true", help="print the AskResponse JSON instead of text")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("stats", help="label and relationship counts")
    p.add_argument("--repo", help="restrict to one repository")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("serve", help="run the HTTP API")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--host", default=None)
    p.add_argument("--reload", action="store_true")
    p.set_defaults(func=cmd_serve)

    for module_name in _PLUGINS:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            log.debug("%s not available: %s", module_name, exc)
            continue
        register = getattr(module, "register", None)
        if register is None:
            log.debug("%s has no register()", module_name)
            continue
        try:
            register(sub)
        except Exception as exc:  # noqa: BLE001 - one broken plugin must not take the CLI down
            log.warning("%s.register failed: %s", module_name, exc)
    return parser


# ------------------------------------------------------------------------------------------------------------------
# commands


def cmd_schema(args: argparse.Namespace) -> int:
    from untangle.graph.db import connect

    graph = connect(require=True)
    try:
        result = graph.ensure_schema()
    finally:
        graph.close()
    print(f"schema ok: {result['constraints']} constraints, {result['indexes']} indexes")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from untangle.answer import service

    mode = "baseline" if args.baseline_only else "both" if args.baseline else "graph"
    response = service.ask(args.question, args.repo, at=args.at, mode=mode)
    if args.json:
        print(json.dumps(response.model_dump(by_alias=True), ensure_ascii=False, indent=2))
    else:
        print(render_ask(response))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    from untangle.answer import service

    stats = service.get_graph().stats(args.repo)
    if args.json:
        print(json.dumps(stats, indent=2))
        return 0
    print(f"nodes: {stats['nodes']}   relationships: {stats['relationships']}" + (f"   repo: {args.repo}" if args.repo else ""))
    for label, n in stats["labels"].items():
        print(f"  {label:<14}{n:>9}")
    print("relationships:")
    for rel, n in stats["relationship_types"].items():
        print(f"  {rel:<14}{n:>9}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from untangle.config import settings

    s = settings()
    uvicorn.run("untangle.api.main:app", host=args.host or s.api_host, port=args.port or s.api_port, reload=args.reload, log_level="info")
    return 0


# ------------------------------------------------------------------------------------------------------------------
# terminal rendering


def _tty() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _tty() else text


def render_ask(r: Any) -> str:
    """Pretty terminal output: answer, confidence, evidence chain, supersession, citations, baseline."""
    lines: list[str] = []
    lines.append(_c("1", f"Q: {r.question}") + f"   ({r.repo}, {r.intent}" + (f", as of {r.at_iso[:10]}" if r.at_iso else "") + ")")
    lines.append("")
    lines.append(_c("93", r.answer) if r.refused else r.answer)
    lines.append("")
    colour = {"high": "92", "medium": "93", "low": "91", "refuse": "91"}[r.confidence.label]
    lines.append(_c(colour, f"confidence {r.confidence.score:.2f} ({r.confidence.label})") + ": " + "; ".join(r.confidence.reasons))
    if r.evidence_chain:
        lines.append("")
        lines.append(_c("1", "evidence chain"))
        for step in r.evidence_chain:
            if step.role == "date":
                lines.append(f"  date       {step.iso}")
            elif step.role == "person":
                lines.append(f"  person     {step.name}" + (f" — {step.why}" if step.why else "") + (f"  [{step.id}]" if step.id else ""))
            else:
                extra = f" ({step.status}, {(step.valid_from_iso or '')[:10]}{' → ' + step.valid_to_iso[:10] if step.valid_to_iso else ''})" if step.role == "decision" else ""
                lines.append(f"  {step.role:<10} {step.title or ''}{extra}  [{step.id}]")
                if step.url:
                    lines.append(f"             {step.url}")
    if r.supersession:
        lines.append("")
        lines.append(_c("1", "supersession"))
        for s in r.supersession:
            lines.append(f"  {(s.at_iso or '')[:10]}  {s.older_text or s.older}")
            lines.append(f"      → {s.newer_text or s.newer}  ({s.signal})")
    if r.citations:
        lines.append("")
        lines.append(_c("1", "citations"))
        for cid, c in r.citations.items():
            lines.append(f"  [{cid}] {c.kind}: {c.title or ''}" + (f"  {c.url}" if c.url else ""))
    if r.why and r.why.cypher:
        lines.append("")
        lines.append(_c("2", "cypher: " + ", ".join(f"{c.name}({c.rows} rows, {c.ms or 0:.0f} ms)" for c in r.why.cypher)))
        lines.append(_c("2", f"llm: {r.why.llm.backend}/{r.why.llm.model} used={r.why.llm.used}   route: {r.why.route}"))
    if r.baseline:
        lines.append("")
        lines.append(_c("1", "baseline (vector-only)"))
        lines.append("  " + r.baseline.answer)
        for ch in r.baseline.chunks[:5]:
            lines.append(f"    {ch.score:.3f} {ch.source_kind or 'chunk'}: {ch.text[:100].replace(chr(10), ' ')}  [{ch.id}]")
        lines.append(_c("2", f"  note: {r.baseline.note}"))
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252; never crash on Devanagari or dashes
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    level = logging.WARNING if args.verbose == 0 else logging.INFO if args.verbose == 1 else logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    try:
        result = func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 - the CLI reports, it does not trace
        if args.verbose:
            log.exception("command failed")
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return int(result or 0)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
