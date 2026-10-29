"""Small, dependency-free shaping helpers for the public health contract."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def shape_health(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Add stable readiness fields while keeping the legacy health fields intact.

    The answer service owns the actual graph probe and backend discovery. This module only
    adds safe readiness fields; it never adds credentials or secret configuration values.
    """
    neo4j = dict(snapshot.get("neo4j") or {})
    llm = dict(snapshot.get("llm") or {})
    embed = dict(snapshot.get("embed") or {})
    sarvam = dict(snapshot.get("sarvam") or {})
    return {
        **dict(snapshot),
        "status": "ok" if bool(snapshot.get("ok")) else "degraded",
        "graph": {
            "ok": bool(neo4j.get("ok")),
            "version": neo4j.get("version"),
            "aura": bool(neo4j.get("aura")),
            "edition": neo4j.get("edition"),
        },
        "optional_backends": {
            "llm": {"backend": llm.get("backend"), "available": bool(llm.get("available"))},
            "embeddings": {"backend": embed.get("backend"), "available": bool(embed.get("available", embed.get("backend")))},
            "sarvam": {"configured": bool(sarvam.get("configured"))},
        },
    }


__all__ = ["shape_health"]
