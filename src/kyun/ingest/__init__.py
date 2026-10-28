"""Repository ingestion: git history, GitHub discussion, documents, symbols, config history and the deterministic
decisions derived from them, loaded into the Kyun graph. Entry point: `kyun.ingest.pipeline.ingest_repo`."""

from kyun.ingest.pipeline import ingest_repo

__all__ = ["ingest_repo"]
