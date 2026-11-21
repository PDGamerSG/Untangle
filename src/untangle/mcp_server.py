"""Untangle as a Model Context Protocol server: the decision graph as memory for coding agents.

Coding agents (Claude Code, Cursor and other MCP clients) connect over Streamable HTTP with a personal access
token. The server is stateless: each POST carries one JSON-RPC message and gets one JSON response, which suits
serverless hosting. Every tool reads or writes the same Neo4j graph the web app uses, so an agent sees cited
decisions, their supersession history and the people behind them, and can record what it decided for the next
agent or engineer.

Protocol notes: requests are answered with `application/json`; notifications and client responses get 202 with no
body; batches are rejected (removed from the protocol in 2025-06-18). Tool failures the agent can correct are
returned as tool results with `isError: true`, as the specification asks, not as protocol errors."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from untangle import __version__, agent_memory
from untangle.answer import service
from untangle.auth.service import User
from untangle.repositories.service import normalize_repository

log = logging.getLogger("untangle.mcp")

PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")
INSTRUCTIONS = (
    "Untangle answers why code is the way it is from a graph of the repository's history: commits, pull requests, "
    "reviews, issues, design documents, configuration and dependency changes, and recorded handover calls. "
    "Before changing a configuration value, dependency version or unusual piece of code, call ask_why or "
    "list_decisions for it. Answers cite their evidence; a refusal means the history does not explain it, so ask the "
    "person suggested by who_to_ask instead of guessing. After you settle a non-obvious decision, record it with "
    "remember_decision so the next agent or engineer can find the reason. Repository names use owner/name; call "
    "list_repositories to see what is indexed."
)


class ToolError(Exception):
    """A problem the agent can fix; returned to it as a tool result with isError."""


def _repo(args: dict[str, Any]) -> str:
    value = args.get("repo")
    if not isinstance(value, str) or not value.strip():
        raise ToolError("repo is required, as owner/name. Call list_repositories to see indexed repositories.")
    try:
        repo = normalize_repository(value)
    except Exception as exc:  # noqa: BLE001 - surface the validation message to the agent
        raise ToolError(str(exc)) from exc
    known = {r.full_name.lower(): r.full_name for r in service.repos()}
    if repo.lower() not in known:
        raise ToolError(f"{repo} is not indexed in Untangle. Call list_repositories, or import it from the web app first.")
    return known[repo.lower()]


def _text(args: dict[str, Any], name: str, *, limit: int, required: bool = True) -> str | None:
    value = args.get(name)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ToolError(f"{name} is required.")
        return None
    if not isinstance(value, str):
        raise ToolError(f"{name} must be a string.")
    if len(value) > limit:
        raise ToolError(f"{name} must be at most {limit} characters.")
    return value.strip()


def _decision_line(d: dict[str, Any]) -> str:
    status = d.get("status") or "active"
    since = (d.get("valid_from_iso") or "")[:10]
    source = (d.get("decided_in") or {}).get("url") or ""
    why = f" Reason: {d['rationale']}" if d.get("rationale") else ""
    agent = " [agent note]" if d.get("kind") == "agent" else ""
    return f"- [{d['id']}] ({status}{', since ' + since if since else ''}){agent} {d.get('text') or d.get('object') or ''}{why}{' ' + source if source else ''}"


# -- tools -------------------------------------------------------------------------------------------------------------


def tool_list_repositories(args: dict[str, Any], user: User) -> tuple[str, dict[str, Any]]:
    repos = [{"repo": r.full_name, "decisions": r.counts.get("decisions", 0), "commits": r.counts.get("commits", 0),
              "indexed_at": r.ingested_at_iso} for r in service.repos()]
    lines = [f"- {r['repo']}: {r['decisions']} decisions, {r['commits']} commits" for r in repos]
    return ("Indexed repositories:\n" + "\n".join(lines)) if lines else "No repositories are indexed yet.", {"repositories": repos}


def tool_ask_why(args: dict[str, Any], user: User) -> tuple[str, dict[str, Any]]:
    repo = _repo(args)
    question = _text(args, "question", limit=2000)
    at = _text(args, "as_of", limit=40, required=False)
    res = service.ask(question, repo, at=at, mode="graph")
    citations = [{"id": cid, "kind": c.kind, "title": c.title, "url": c.url} for cid, c in res.citations.items()]
    lines = [res.answer]
    if res.refused:
        if res.closest:
            lines.append("Closest related: " + ", ".join(e.path or e.key or e.name or e.id for e in res.closest))
        if res.ask:
            lines.append(f"Person to ask: {res.ask.name}" + (f" ({res.ask.why})" if res.ask.why else ""))
    else:
        lines.append(f"Confidence: {res.confidence.label} ({res.confidence.score:.2f})")
        for s in res.supersession:
            lines.append(f"Replaced on {(s.at_iso or '')[:10]}: {s.older_text or s.older} -> {s.newer_text or s.newer}")
        for c in citations:
            lines.append(f"[{c['id']}] {c['kind']}: {c['title'] or ''} {c['url'] or ''}".rstrip())
    structured = {"repo": repo, "answer": res.answer, "refused": res.refused, "confidence": res.confidence.score,
                  "citations": citations, "closest": [e.model_dump() for e in res.closest], "ask": res.ask.model_dump() if res.ask else None}
    return "\n".join(lines), structured


def _entity_for(repo: str, subject: str) -> tuple[dict[str, Any], Any]:
    hits = service.search(repo, subject)
    exact = [e for e in hits.entities if subject in (e.path, e.key, e.name)]
    chosen = (exact or hits.entities)[:1]
    if not chosen:
        raise ToolError(f"Nothing named '{subject}' was found in {repo}. Try search_repository with a shorter term.")
    entity = service.entity(chosen[0].id)
    return chosen[0].model_dump(), entity


def tool_list_decisions(args: dict[str, Any], user: User) -> tuple[str, dict[str, Any]]:
    repo = _repo(args)
    subject = _text(args, "subject", limit=300)
    hit, entity = _entity_for(repo, subject)
    decisions = [d.model_dump() for d in entity.decisions[:25]]
    name = hit.get("path") or hit.get("key") or hit.get("name")
    if not decisions:
        return f"No decisions are recorded about {name} ({hit['label']}).", {"entity": hit, "decisions": []}
    text = f"Decisions about {name} ({hit['label']}), active first:\n" + "\n".join(_decision_line(d) for d in decisions)
    return text, {"entity": hit, "decisions": decisions}


def tool_decision_timeline(args: dict[str, Any], user: User) -> tuple[str, dict[str, Any]]:
    repo = _repo(args)
    at = _text(args, "as_of", limit=40, required=False)
    snapshot = service.timeline(repo, at)
    active = [d.model_dump() for d in snapshot.active[:30]]
    changed = [d.model_dump() for d in snapshot.superseded_since[:15]]
    text = f"Decisions in force on {snapshot.at_iso[:10]} ({len(snapshot.active)} total, first 30 shown):\n"
    text += "\n".join(_decision_line(d) for d in active) or "- none"
    if changed:
        text += "\n\nReplaced since then:\n" + "\n".join(_decision_line(d) for d in changed)
    return text, {"at": snapshot.at_iso, "active": active, "superseded_since": changed}


def tool_who_to_ask(args: dict[str, Any], user: User) -> tuple[str, dict[str, Any]]:
    repo = _repo(args)
    subject = _text(args, "subject", limit=300)
    hit, entity = _entity_for(repo, subject)
    people = [p.model_dump() for p in entity.people[:5]]
    name = hit.get("path") or hit.get("key") or hit.get("name")
    if not people:
        return f"No one is recorded for {name}.", {"entity": hit, "people": []}
    lines = [f"- {p.get('name') or p.get('login') or p['id']}: {p.get('why') or ''}".rstrip(": ") for p in people]
    return f"People most likely to know about {name}:\n" + "\n".join(lines) + "\nThis ranks recorded history, not current availability.", {"entity": hit, "people": people}


def tool_search_repository(args: dict[str, Any], user: User) -> tuple[str, dict[str, Any]]:
    repo = _repo(args)
    query = _text(args, "query", limit=300)
    hits = service.search(repo, query)
    entities = [e.model_dump() for e in hits.entities[:15]]
    people = [p.model_dump() for p in hits.people[:5]]
    lines = [f"- {e['label']}: {e.get('path') or e.get('key') or e.get('name')}" for e in entities]
    lines += [f"- Person: {p.get('name') or p.get('login')}" for p in people]
    return ("Matches:\n" + "\n".join(lines)) if lines else f"Nothing in {repo} matches '{query}'.", {"entities": entities, "people": people}


def tool_remember_decision(args: dict[str, Any], user: User) -> tuple[str, dict[str, Any]]:
    repo = _repo(args)
    try:
        saved = agent_memory.remember(
            service.get_graph(), user, repo, _text(args, "subject", limit=300), _text(args, "decision", limit=agent_memory.MAX_DECISION),
            rationale=_text(args, "rationale", limit=agent_memory.MAX_RATIONALE, required=False),
            topic=_text(args, "topic", limit=60, required=False), source_url=_text(args, "source_url", limit=500, required=False),
        )
    except agent_memory.MemoryProblem as exc:
        raise ToolError(str(exc)) from exc
    note = f" It replaces {len(saved['supersedes'])} earlier note(s) on this topic." if saved["supersedes"] else ""
    return f"Recorded [{saved['id']}] about {saved['subject']} (topic: {saved['topic']}).{note}", saved


def tool_recall_agent_notes(args: dict[str, Any], user: User) -> tuple[str, dict[str, Any]]:
    repo = _repo(args)
    notes = agent_memory.memories(service.get_graph(), repo, limit=20)
    if not notes:
        return f"No coding agent has recorded decisions in {repo} yet.", {"notes": []}
    lines = [f"- [{n['id']}] ({n['status']}, {n['recorded_at_iso'][:10]}) {', '.join(n['about'])} / {n['topic']}: {n['decision']}" for n in notes]
    return "Notes recorded by coding agents, newest first:\n" + "\n".join(lines), {"notes": notes}


_REPO = {"type": "string", "description": "Repository as owner/name, for example knadh/listmonk.", "maxLength": 200}
_AS_OF = {"type": "string", "description": "Optional date (YYYY-MM-DD) to answer as of that day.", "maxLength": 40}
_SUBJECT = {"type": "string", "description": "A file path, config key, dependency or module name.", "maxLength": 300}
_READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

TOOLS: dict[str, dict[str, Any]] = {
    "list_repositories": {
        "title": "List indexed repositories", "fn": tool_list_repositories, "annotations": _READ,
        "description": "List the repositories Untangle has indexed, with decision and commit counts.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "ask_why": {
        "title": "Ask why the code is like this", "fn": tool_ask_why, "annotations": _READ, "charge": True,
        "description": "Explain why something in a repository is the way it is, from cited evidence in its history (commits, "
                       "pull requests, issues, documents, handover calls). Refuses, with the closest related items and a person "
                       "to ask, when the history does not explain it.",
        "inputSchema": {"type": "object", "properties": {"repo": _REPO, "question": {"type": "string", "maxLength": 2000,
                        "description": "A concrete question naming a value, dependency, file or module."}, "as_of": _AS_OF},
                        "required": ["repo", "question"], "additionalProperties": False},
    },
    "list_decisions": {
        "title": "List decisions about a subject", "fn": tool_list_decisions, "annotations": _READ,
        "description": "List recorded decisions about one file, config key, dependency or module, with status, dates, reasons "
                       "and sources. Superseded decisions are kept so you can see what changed.",
        "inputSchema": {"type": "object", "properties": {"repo": _REPO, "subject": _SUBJECT}, "required": ["repo", "subject"], "additionalProperties": False},
    },
    "decision_timeline": {
        "title": "Decisions in force on a date", "fn": tool_decision_timeline, "annotations": _READ,
        "description": "The decisions in force on a date (today by default) and those replaced since then.",
        "inputSchema": {"type": "object", "properties": {"repo": _REPO, "as_of": _AS_OF}, "required": ["repo"], "additionalProperties": False},
    },
    "who_to_ask": {
        "title": "Who knows about this", "fn": tool_who_to_ask, "annotations": _READ,
        "description": "The people with the most relevant history (authored, reviewed, discussed or stated decisions) for a file, "
                       "config key, dependency or module.",
        "inputSchema": {"type": "object", "properties": {"repo": _REPO, "subject": _SUBJECT}, "required": ["repo", "subject"], "additionalProperties": False},
    },
    "search_repository": {
        "title": "Search files, keys and people", "fn": tool_search_repository, "annotations": _READ,
        "description": "Find files, config keys, dependencies, modules, symbols and people by name in an indexed repository.",
        "inputSchema": {"type": "object", "properties": {"repo": _REPO, "query": {"type": "string", "maxLength": 300}},
                        "required": ["repo", "query"], "additionalProperties": False},
    },
    "remember_decision": {
        "title": "Record a decision in the graph", "fn": tool_remember_decision, "write": True,
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
        "description": "Record a non-obvious decision you made or confirmed while working, against the file, config key, "
                       "dependency or module it is about. It is stored in the shared decision graph, labelled as an agent note "
                       "and attributed to your user, and a later note on the same subject and topic supersedes it.",
        "inputSchema": {"type": "object", "properties": {
            "repo": _REPO, "subject": _SUBJECT,
            "decision": {"type": "string", "maxLength": 500, "description": "What was decided, in one or two sentences."},
            "rationale": {"type": "string", "maxLength": 1500, "description": "Why, including the constraint or incident behind it."},
            "topic": {"type": "string", "maxLength": 60, "description": "Short topic, for example 'retry policy'. Notes with the same subject and topic supersede each other."},
            "source_url": {"type": "string", "maxLength": 500, "description": "Optional https link to the pull request, issue or document behind it."},
        }, "required": ["repo", "subject", "decision"], "additionalProperties": False},
    },
    "recall_agent_notes": {
        "title": "Recall notes from coding agents", "fn": tool_recall_agent_notes, "annotations": _READ,
        "description": "Recent decisions that coding agents recorded in a repository, newest first, including replaced ones.",
        "inputSchema": {"type": "object", "properties": {"repo": _REPO}, "required": ["repo"], "additionalProperties": False},
    },
}


def tool_list() -> list[dict[str, Any]]:
    return [{"name": name, "title": t["title"], "description": t["description"], "inputSchema": t["inputSchema"],
             "annotations": t["annotations"]} for name, t in TOOLS.items()]


def _result(id_: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _error(id_: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def handle(message: Any, user: User, *, charge: Callable[[str], None]) -> dict[str, Any] | None:
    """One JSON-RPC message in, one response out (None for notifications and client responses)."""
    if isinstance(message, list):
        return _error(None, -32600, "Batched requests are not supported; send one JSON-RPC message per request.")
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid JSON-RPC 2.0 message.")
    method, id_ = message.get("method"), message.get("id")
    if method is None:  # a response to a server request; this server sends none
        return None
    if "id" not in message:  # notification, e.g. notifications/initialized
        return None
    params = message.get("params") or {}
    if not isinstance(params, dict):
        return _error(id_, -32602, "params must be an object.")
    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return _result(id_, {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                             "serverInfo": {"name": "untangle", "title": "Untangle decision memory", "version": __version__},
                             "instructions": INSTRUCTIONS})
    if method == "ping":
        return _result(id_, {})
    if method == "tools/list":
        return _result(id_, {"tools": tool_list()})
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        tool = TOOLS.get(name) if isinstance(name, str) else None
        if tool is None:
            return _error(id_, -32602, f"Unknown tool: {name!r}.")
        if not isinstance(args, dict):
            return _error(id_, -32602, "arguments must be an object.")
        try:
            charge("ask" if tool.get("charge") else "write" if tool.get("write") else "read")
            text, structured = tool["fn"](args, user)
        except ToolError as exc:
            return _result(id_, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
        except (service.NotFound, ValueError) as exc:
            return _result(id_, {"content": [{"type": "text", "text": str(exc)[:500]}], "isError": True})
        return _result(id_, {"content": [{"type": "text", "text": text}], "structuredContent": structured, "isError": False})
    return _error(id_, -32601, f"Method not found: {method}.")
