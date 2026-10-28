"""Repository ingestion: git history, GitHub discussion, documents, symbols, config history and the deterministic
decisions derived from them, loaded into the Untangle graph. Entry point: `untangle.ingest.pipeline.ingest_repo`."""

from untangle.ingest.pipeline import ingest_repo

__all__ = ["ingest_repo"]
