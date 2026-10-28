"""`untangle eval --repo owner/name --gold eval/gold/<name>.yaml [--out eval/out/<name>.md] [--modes graph,baseline]`.
The CLI owner imports `register(subparsers)`; `python -m untangle.eval.cli` runs it standalone."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from untangle.eval.harness import DEFAULT_MODES, run_eval

log = logging.getLogger("untangle.eval.cli")


def run(args: argparse.Namespace) -> int:
    modes = tuple(m.strip() for m in (args.modes or ",".join(DEFAULT_MODES)).split(",") if m.strip())
    out = args.out or (Path("eval") / "out" / f"{Path(args.gold).stem}.md")
    report = run_eval(args.gold, modes=modes, out=out, repo=args.repo)
    if args.json:
        print(json.dumps({k: v for k, v in report.items() if k != "runs"}, ensure_ascii=False, indent=2, default=str))
        return 0
    print(f"wrote {report['out']} ({report['questions']} questions x {len(modes)} modes)")
    for mode in modes:
        s = report["summary"][mode]["verified"]
        ev, sup, per = s["evidence_accuracy"], s["supersession_correctness"], s["person_hit_rate"]
        ref = s["refusal"]
        fmt = lambda b: "n/a" if not b["n"] else f"{b['hits']}/{b['n']}"  # noqa: E731
        pr = "n/a" if ref["precision"] is None else f"{ref['precision']:.2f}"
        rc = "n/a" if ref["recall"] is None else f"{ref['recall']:.2f}"
        p50 = "n/a" if s["latency_ms"]["p50"] is None else f"{s['latency_ms']['p50']:.0f} ms"
        print(f"  {mode:>8}: evidence {fmt(ev)}  supersession {fmt(sup)}  refusal P/R {pr}/{rc}  person {fmt(per)}  p50 {p50}  errors {s['errors']}")
    return 0


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = subparsers.add_parser("eval", help="run the gold questions through graph and vector-only answering and write a report")
    p.add_argument("--repo", help="owner/name (defaults to the gold file's repo)")
    p.add_argument("--gold", required=True, help="eval/gold/<name>.yaml")
    p.add_argument("--out", help="Markdown report path (default eval/out/<name>.md; a .json is written next to it)")
    p.add_argument("--modes", help="comma-separated subset of graph,baseline (default both)")
    p.add_argument("--json", action="store_true", help="print the summary as JSON")
    p.set_defaults(func=run)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="untangle")
    register(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
