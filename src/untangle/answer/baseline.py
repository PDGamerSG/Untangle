"""The vector-only baseline for the side-by-side demo: embed the question, pull the nearest chunks from the
`chunk_embedding` index (`cypher/50_vector_chunks.cypher`), and answer from the chunks alone. No graph walk, so no
supersession awareness and no graph-derived confidence; the response says so."""

from __future__ import annotations

import logging
import math
from typing import Any

from kyun.answer.models import Baseline, BaselineChunk
from kyun.answer.retrieve import Recorder
from kyun.answer.text import squash
from kyun.embed import Embedder, make_embedder
from kyun.graph.db import Graph, Neo4jError
from kyun.llm import LLM, LLMUnavailable

log = logging.getLogger("kyun.answer.baseline")

NOTE = "vector-only, no graph: no supersession, no confidence"
FIRST_K = 500  # candidates asked from the HNSW index before the repo filter
RETRY_K = 5000  # second attempt when the first left fewer than three rows for the repo

BASELINE_SYSTEM = """You answer questions about a software repository using ONLY the passages given. Each passage has an id in square brackets. Cite the id after each claim. At most five sentences, plain text. If the passages do not answer the question, say so in one sentence. Never invent dates, people or reasons."""


def baseline(
    graph: Graph, repo: str, question: str, *, llm: LLM | None = None, embedder: Embedder | None = None, k: int = 8,
    recorder: Recorder | None = None,
) -> Baseline:
    rec = recorder or Recorder(graph)
    embedder = embedder or make_embedder()
    vector = embedder.embed_one(question)
    if not vector or math.sqrt(sum(x * x for x in vector)) == 0.0:
        return Baseline(answer="The question has no searchable words for the vector index.", chunks=[], note=NOTE)
    try:
        # The vector index is global and cannot pre-filter by repo, so a small repository's chunks can be crowded out
        # of the top candidates by a large one; ask generously and widen once when the repo filter leaves too few.
        rows = rec.run("vector_chunks", {"q": vector, "k": max(k * 50, FIRST_K), "repo": repo, "limit": k})
        if len(rows) < min(k, 3):
            rows = rec.run("vector_chunks", {"q": vector, "k": RETRY_K, "repo": repo, "limit": k})
    except Neo4jError as exc:
        log.warning("vector baseline unavailable: %s", exc)
        return Baseline(answer=f"The vector index is not usable ({exc.code if hasattr(exc, 'code') else type(exc).__name__}).", chunks=[], note=NOTE)
    chunks = [
        BaselineChunk(id=r["id"], text=r.get("text") or "", source_kind=r.get("source_kind"), score=float(r.get("score") or 0.0), source_id=r.get("source_id"))
        for r in rows
    ]
    if not chunks:
        return Baseline(answer="No indexed passage of this repository is close to the question.", chunks=[], note=NOTE)
    answer = _compose(question, rows, llm)
    return Baseline(answer=answer, chunks=chunks, note=NOTE)


def _compose(question: str, rows: list[dict[str, Any]], llm: LLM | None) -> str:
    listing = "\n".join(f"- [{r['id']}] ({r.get('source_kind') or 'chunk'}) {squash(r.get('text'), 600)}" for r in rows)
    if llm is not None:
        try:
            text = llm.complete(BASELINE_SYSTEM, f"Question: {question}\n\nPASSAGES:\n{listing}\n\nAnswer in at most five sentences, citing passage ids.", temperature=0.2, max_tokens=500)
            if text.strip():
                return text.strip()
        except LLMUnavailable:
            pass
        except Exception as exc:  # noqa: BLE001
            log.warning("baseline model failed: %s", exc)
    bits = [f"({i}) {r.get('source_kind') or 'chunk'}: {squash(r.get('text'), 200)} [{r['id']}]" for i, r in enumerate(rows[:5], 1)]
    return "Closest passages by embedding similarity, best first: " + " ".join(bits)


__all__ = ["BASELINE_SYSTEM", "NOTE", "baseline"]
