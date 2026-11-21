"""The public health contract: readiness only, with no hosts, model names, versions or error text."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def shape_health(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Reduce the answer service's internal snapshot to what an anonymous visitor may see.

    `/health` is public so the sign-in page can show whether the service is up. It reports whether each part is
    ready and nothing that would help locate or fingerprint the database or the hosted model."""
    neo4j = dict(snapshot.get("neo4j") or {})
    llm = dict(snapshot.get("llm") or {})
    embed = dict(snapshot.get("embed") or {})
    sarvam = dict(snapshot.get("sarvam") or {})
    graph_ok = bool(neo4j.get("ok"))
    llm_backend = "fake" if llm.get("backend") == "fake" else "hosted"
    embed_backend = "fake" if embed.get("backend") == "fake" else "local"
    embed_ok = bool(embed.get("available", embed.get("backend")))
    return {
        "ok": bool(snapshot.get("ok")),
        "status": "ok" if bool(snapshot.get("ok")) else "degraded",
        "version": snapshot.get("version"),
        "neo4j": {"ok": graph_ok, "aura": bool(neo4j.get("aura"))},
        "graph": {"ok": graph_ok, "aura": bool(neo4j.get("aura"))},
        "llm": {"backend": llm_backend, "available": bool(llm.get("available"))},
        "embed": {"backend": embed_backend, "dim": embed.get("dim"), "available": embed_ok},
        "sarvam": {"configured": bool(sarvam.get("configured"))},
        "optional_backends": {
            "llm": {"backend": llm_backend, "available": bool(llm.get("available"))},
            "embeddings": {"backend": embed_backend, "available": embed_ok},
            "sarvam": {"configured": bool(sarvam.get("configured"))},
        },
    }


__all__ = ["shape_health"]
