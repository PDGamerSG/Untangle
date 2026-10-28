"""`kyun ingest owner/name [--max-commits N] [--since YYYY-MM-DD] [--max-prs N] [--no-github] [--no-embed]
[--llm-prs N] [--reset] [--json]` (CONTRACTS §5). `kyun.cli` imports `register` and adds it to its subparsers."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from kyun.graph.db import GraphUnavailable, connect


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("ingest", help="ingest a GitHub repository's history into the graph")
    p.add_argument("repo", metavar="owner/name", help="GitHub repository, e.g. knadh/listmonk")
    p.add_argument("--max-commits", type=int, default=None, metavar="N", help="only the most recent N commits")
    p.add_argument("--since", default=None, metavar="YYYY-MM-DD", help="only commits since this date")
    p.add_argument("--max-prs", type=int, default=None, metavar="N", help="only the N most recently updated pull requests")
    p.add_argument("--no-github", action="store_true", help="skip pull requests, reviews, comments and issues")
    p.add_argument("--no-embed", action="store_true", help="write chunks without embeddings")
    p.add_argument("--llm-prs", type=int, default=0, metavar="N", help="extract rationale from the N most-discussed merged PRs with the LLM")
    p.add_argument("--reset", action="store_true", help="delete everything already ingested for this repository first")
    p.add_argument("--json", action="store_true", help="print the summary as JSON")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from kyun.ingest.pipeline import ingest_repo

    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if "/" not in args.repo:
        print(f"expected owner/name, got {args.repo!r}", file=sys.stderr)
        return 2
    try:
        graph = connect(require=True)
    except GraphUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        graph.ensure_schema()
        summary = ingest_repo(
            args.repo, graph=graph, since=args.since, max_commits=args.max_commits, max_prs=args.max_prs, github=not args.no_github,
            embed=not args.no_embed, llm_prs=args.llm_prs, reset=args.reset, progress=lambda msg: print(msg, file=sys.stderr),
        )
    finally:
        graph.close()
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        stats = summary["stats"]
        print(f"{summary['repo']} @ {summary['head_sha'][:10]}: {summary['commits']} commits, {summary['prs']} PRs, {summary['issues']} issues, "
              f"{summary['decisions']['recorded']} decisions, {summary['chunks']} chunks -> {stats['nodes']} nodes, "
              f"{stats['relationships']} relationships in {summary['total_seconds']:.0f}s")
    return 0


__all__ = ["register", "run"]
