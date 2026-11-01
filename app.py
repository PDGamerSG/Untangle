"""Vercel service entrypoint, including the shared-domain /api prefix.

The unprefixed mount preserves the original API hostname during migration.
The CLI continues to expose the underlying application on its own port.
"""

from fastapi import FastAPI

from untangle.api.main import app as api

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
app.mount("/api", api)
app.mount("/", api)

__all__ = ["app"]
