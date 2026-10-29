"""Vercel entrypoint; the CLI and deployment share the same FastAPI application."""

from untangle.api.main import app

__all__ = ["app"]
