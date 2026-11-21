"""Response headers for every API response.

The web app's pages get their headers from `web/next.config.ts`; Vercel routes `/api/*` straight to this service,
so the API sets its own. API responses are JSON or downloads and never need scripts, frames or styles."""

from __future__ import annotations

from fastapi import FastAPI, Request

API_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    # Answers depend on the signed-in user's session; no shared cache may keep them.
    "Cache-Control": "no-store",
}


def add_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        for name, value in API_HEADERS.items():
            response.headers.setdefault(name, value)
        return response
