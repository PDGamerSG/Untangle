"""Decision memory for coding agents, stored in the same Neo4j graph as repository history.

An agent that settles something while working ("keep retry_limit at 3 until the provider fixes duplicate
deliveries") records it against the file, config key, dependency or module it is about. The note becomes a
`Decision {kind: 'agent'}` with an `ABOUT` edge, so Ask, Timeline and the agent tools all see it. A later note on
the same subject and topic supersedes the earlier one through the normal `SUPERSEDES` rule, keeping the history.
Agent notes use their own `agent|…` keys, so they can never replace a decision taken from the code history, and
answers rank repository evidence ahead of them."""

from __future__ import annotations

import re
import time
import unicodedata
from typing import Any
from urllib.parse import urlsplit

from untangle import ids
from untangle.answer.text import iso
from untangle.auth.service import User
from untangle.graph.db import Graph

ENTITY_LABELS = ("File", "ConfigKey", "Dependency", "Module", "Symbol")
MAX_DECISION = 500
MAX_RATIONALE = 1500


class MemoryProblem(ValueError):
    """A request the agent can correct; the message says how."""


def _clean(value: str | None, limit: int) -> str:
    text = " ".join(unicodedata.normalize("NFKC", value or "").split())
    return "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")[:limit]


def _topic(value: str | None) -> str:
    topic = re.sub(r"[^a-z0-9]+", "-", _clean(value, 60).lower()).strip("-")
    return topic or "note"


def _source(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value.strip())
    if parts.scheme != "https" or not parts.netloc or len(value) > 500:
        raise MemoryProblem("source_url must be an https:// link, such as the pull request or issue behind the decision.")
    return value.strip()


def resolve_subject(graph: Graph, repo: str, subject: str) -> dict[str, Any]:
    """The repository entity an agent names by path, config key, dependency or module name (exact match first)."""
    wanted = _clean(subject, 300)
    if not wanted:
        raise MemoryProblem("subject is required: a file path, config key, dependency or module in the repository.")
    rows = graph.read(
        # Each kind is matched on its own identifying field: a config key's `path` is the file that sets it, so
        # "config.toml" must resolve to the file, not to a key inside it.
        """MATCH (e:File|ConfigKey|Dependency|Module|Symbol {repo: $repo})
           WITH e, CASE
             WHEN e:File AND e.path = $s THEN 0
             WHEN e:ConfigKey AND (e.key = $s OR e.path + '::' + e.key = $s) THEN 1
             WHEN e:Dependency AND e.name = $s THEN 2
             WHEN e:Module AND (e.path = $s OR e.name = $s) THEN 3
             WHEN e:Symbol AND e.name = $s THEN 4
           END AS rank
           WHERE rank IS NOT NULL
           RETURN e.id AS id, [l IN labels(e) WHERE l IN $labels][0] AS label,
                  CASE WHEN e:ConfigKey THEN e.path + '::' + e.key ELSE coalesce(e.path, e.name, e.key) END AS name,
                  e.path AS path, e.key AS key
           ORDER BY rank
           LIMIT 1""",
        {"repo": repo, "s": wanted, "labels": list(ENTITY_LABELS)},
    ).records
    if not rows:
        raise MemoryProblem(f"'{wanted}' is not a file, config key, dependency or module in {repo}. Use search_repository to find the exact name.")
    return rows[0]


def remember(graph: Graph, user: User, repo: str, subject: str, decision: str, *, rationale: str | None = None,
             topic: str | None = None, source_url: str | None = None, now_ms: int | None = None) -> dict[str, Any]:
    text = _clean(decision, MAX_DECISION)
    if len(text) < 8:
        raise MemoryProblem("decision must say what was decided, in at least a short sentence.")
    why = _clean(rationale, MAX_RATIONALE) or None
    source = _source(source_url)
    entity = resolve_subject(graph, repo, subject)
    now = int(now_ms or time.time() * 1000)
    key = f"agent|{entity['id']}|{_topic(topic)}"
    decision_id = ids.decision_id(repo, "agent", key, f"{user.id}:{now}")
    row = {
        "id": decision_id, "repo": repo, "kind": "agent", "key": key, "subject": entity["name"], "predicate": _topic(topic),
        "object": text, "text": f"{text} (recorded by a coding agent for {user.name})", "rationale": why,
        "valid_from": now, "confidence": 0.55, "signal": "agent_memory", "created_at": now,
    }
    result = graph.run_named("record_decision", {"rows": [row], "now": now}, write=True).records
    graph.query(
        "MATCH (d:Decision {id: $id}) SET d.recorded_by = $user_id, d.recorded_by_name = $name, d.source_url = $source",
        {"id": decision_id, "user_id": user.id, "name": user.name, "source": source},
    )
    graph.run_named("link_decision", {"rows": [{"decision_id": decision_id, "rel": "ABOUT", "target_id": entity["id"], "props": {}}], "now": now}, write=True)
    superseded = result[0]["superseded"] if result else []
    return {"id": decision_id, "subject": entity["name"], "subject_kind": entity["label"], "topic": row["predicate"],
            "decision": text, "rationale": why, "source_url": source, "recorded_at_iso": iso(now), "supersedes": superseded}


def memories(graph: Graph, repo: str, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = graph.run_named("agent_memories", {"repo": repo, "limit": max(1, min(limit, 50))}).records
    return [{**{k: v for k, v in r.items() if k != "valid_from"}, "recorded_at_iso": iso(r["valid_from"])} for r in rows]
