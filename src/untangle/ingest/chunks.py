"""Chunk rows for the vector-only baseline and chunk recall: ~800-character windows over commit messages,
PR and issue title+body, comment bodies and document sections, embedded with `untangle.embed.make_embedder()`.

Chunks are the only nodes that carry vectors; `--no-embed` leaves `embedding` null, and the vector index
simply has nothing to return (the graph answer path never needs it)."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from untangle import ids
from untangle.embed import Embedder
from untangle.ingest.docs import DocumentRecord
from untangle.ingest.git_history import CommitRecord
from untangle.ingest.github_api import IssueRecord, PullRecord

log = logging.getLogger("untangle.ingest.chunks")

CHUNK_CHARS = 800
MIN_CHUNK_CHARS = 20
MAX_CHUNKS_PER_SOURCE = 8
EMBED_BATCH = 128

_MERGE_MESSAGE = re.compile(r"^Merge (pull request|branch|remote-tracking branch|tag)\b", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.!?।])\s+")
_WS = re.compile(r"[ \t]+")


@dataclass(slots=True)
class ChunkSource:
    source_id: str
    source_kind: str  # pr | issue | comment | commit | document
    text: str
    created_at: int | None


def _clean(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text or "", flags=re.S)
    text = re.sub(r"\r\n?", "\n", text)
    text = _WS.sub(" ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def chunk_text(text: str, size: int = CHUNK_CHARS, max_chunks: int = MAX_CHUNKS_PER_SOURCE) -> list[str]:
    """Windows of at most `size` characters that prefer paragraph, then sentence, then hard boundaries."""
    text = _clean(text)
    if len(text) < MIN_CHUNK_CHARS:
        return []
    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if len(current.strip()) >= MIN_CHUNK_CHARS:
            chunks.append(current.strip())
        current = ""

    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        pieces = [paragraph] if len(paragraph) <= size else _SENTENCE.split(paragraph)
        for piece in pieces:
            while len(piece) > size:  # hard wrap a monster sentence / code block
                if current:
                    flush()
                chunks.append(piece[:size].strip())
                piece = piece[size:]
            if len(current) + len(piece) + 1 > size and current:
                flush()
            current = f"{current}\n{piece}" if current else piece
        if len(chunks) >= max_chunks:
            break
    flush()
    return chunks[:max_chunks]


def build_sources(
    repo: str,
    *,
    commits: Iterable[CommitRecord] = (),
    prs: Iterable[PullRecord] = (),
    issues: Iterable[IssueRecord] = (),
    documents: Iterable[DocumentRecord] = (),
) -> Iterator[ChunkSource]:
    for c in commits:
        if c.is_merge and _MERGE_MESSAGE.match(c.message or ""):
            continue
        yield ChunkSource(ids.commit_id(repo, c.sha), "commit", c.message, c.authored_at)
    for pr in prs:
        yield ChunkSource(ids.pr_id(repo, pr.number), "pr", f"{pr.title}\n\n{pr.body}", pr.created_at)
        for r in pr.reviews:
            if r.body.strip():
                yield ChunkSource(ids.comment_id(repo, "pr_review", r.id), "comment", r.body, r.submitted_at)
        for c in pr.review_comments + pr.comments:
            yield ChunkSource(ids.comment_id(repo, c.kind, c.id), "comment", c.body, c.created_at)
    for issue in issues:
        yield ChunkSource(ids.issue_id(repo, issue.number), "issue", f"{issue.title}\n\n{issue.body}", issue.created_at)
        for c in issue.comments:
            yield ChunkSource(ids.comment_id(repo, c.kind, c.id), "comment", c.body, c.created_at)
    for doc in documents:
        sections = doc.sections or [("", doc.text)]
        body = "\n\n".join(f"{h}\n{b}" if h else b for h, b in sections)
        yield ChunkSource(ids.document_id(repo, doc.path), "document", f"{doc.title}\n\n{body}", doc.date)


def chunk_rows(repo: str, sources: Iterable[ChunkSource], embedder: Embedder | None = None) -> list[dict[str, Any]]:
    """Rows for `16_upsert_chunks`; embeddings are computed in batches when an embedder is given."""
    rows: list[dict[str, Any]] = []
    for src in sources:
        for seq, text in enumerate(chunk_text(src.text)):
            rows.append({
                "id": ids.chunk_id(src.source_id, seq), "repo": repo, "text": text, "source_id": src.source_id,
                "source_kind": src.source_kind, "seq": seq, "created_at": src.created_at, "embedding": None,
            })
    if embedder is not None and rows:
        for start in range(0, len(rows), EMBED_BATCH):
            batch = rows[start : start + EMBED_BATCH]
            vectors = embedder.embed([r["text"] for r in batch])
            for row, vec in zip(batch, vectors, strict=True):
                row["embedding"] = [float(x) for x in vec]
        log.info("embedded %d chunks with %s (%d dims)", len(rows), embedder.backend, embedder.dim)
    return rows


__all__ = ["ChunkSource", "build_sources", "chunk_rows", "chunk_text"]
