"""The built-in agent on the Agents page: the deployment's configured Claude model with Untangle's read-only tools.

People can ask it about a repository without creating a token or running their own agent. It uses the same tool
functions coding agents reach over MCP (`untangle.mcp_server.TOOLS`), minus the one that writes to the graph, and
the same per-account limits. The loop runs on the Messages API in this process because every tool reads this
deployment's own graph."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from untangle import mcp_server
from untangle.answer import service
from untangle.auth.service import User
from untangle.config import settings
from untangle.llm import DEFAULT_MODELS

log = logging.getLogger("untangle.agent_chat")

MAX_TURNS = 12  # earlier messages the browser may send back
MAX_MESSAGE = 4000
MAX_TOOL_ROUNDS = 6
MAX_TOOL_TEXT = 8000
READ_ONLY_TOOLS = tuple(name for name, tool in mcp_server.TOOLS.items() if not tool.get("write"))

SYSTEM = (
    "You are the Untangle assistant. You help engineers understand why code in an indexed repository is the way it "
    "is, using only the tools provided: they read a graph of the repository's commits, pull requests, reviews, issues, "
    "documents, configuration and dependency changes, and recorded handover calls.\n"
    "Rules:\n"
    "- Look things up with the tools before answering; do not answer from general knowledge about a project.\n"
    "- Cite evidence the tools return: commit short SHAs, pull request or issue numbers, document paths, dates, people.\n"
    "- When the tools do not explain something, say so plainly and name the person who_to_ask suggests.\n"
    "- Keep answers short: a direct answer first, then the evidence as a brief list. Use Markdown sparingly.\n"
    "- You cannot change code or record decisions here."
)


class AgentUnavailable(RuntimeError):
    pass


class AgentLimit(RuntimeError):
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _client():
    s = settings()
    if s.llm_backend != "anthropic" or not s.anthropic_api_key:
        raise AgentUnavailable("The built-in agent is not available on this deployment. Connect your own agent below.")
    import anthropic
    return anthropic.Anthropic(api_key=s.anthropic_api_key, timeout=60.0, max_retries=1), s.llm_model or DEFAULT_MODELS["anthropic"]


def tool_definitions() -> list[dict[str, Any]]:
    return [{"name": name, "description": mcp_server.TOOLS[name]["description"], "input_schema": mcp_server.TOOLS[name]["inputSchema"]}
            for name in READ_ONLY_TOOLS]


def _history(messages: list[dict[str, str]], repo: str | None) -> list[dict[str, Any]]:
    turns = [m for m in messages if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str) and m["content"].strip()]
    turns = turns[-MAX_TURNS:]
    while turns and turns[0]["role"] != "user":
        turns = turns[1:]
    if not turns or turns[-1]["role"] != "user":
        raise ValueError("Send a question as the last message.")
    history = [{"role": m["role"], "content": m["content"][:MAX_MESSAGE]} for m in turns]
    if repo:
        history[-1]["content"] = f"[Selected repository: {repo}]\n{history[-1]['content']}"
    return history


def _run_tool(name: str, args: Any, user: User, charge: Callable[[str], None]) -> tuple[str, bool]:
    tool = mcp_server.TOOLS.get(name)
    if name not in READ_ONLY_TOOLS or tool is None:
        return f"Unknown tool: {name}", True
    if not isinstance(args, dict):
        return "Tool input must be an object.", True
    try:
        charge("ask" if tool.get("charge") else "read")
        text, _ = tool["fn"](args, user)
        return text[:MAX_TOOL_TEXT], False
    except AgentLimit:
        raise
    except mcp_server.ToolError as exc:
        return str(exc)[:500], True
    except (service.NotFound, ValueError) as exc:
        return str(exc)[:500], True


def _summary(args: Any) -> str:
    if not isinstance(args, dict):
        return ""
    parts = [str(v) for k, v in args.items() if k != "repo" and isinstance(v, (str, int))]
    return " · ".join(parts)[:160]


def chat(messages: list[dict[str, str]], repo: str | None, user: User, *, charge: Callable[[str], None], client=None) -> dict[str, Any]:
    """Answer the last user message. Returns the reply text and the tool calls made, for display."""
    history = _history(messages, repo)
    if client is None:
        client, model = _client()
    else:
        model = settings().llm_model or DEFAULT_MODELS["anthropic"]
    steps: list[dict[str, Any]] = []
    response = None
    for _ in range(MAX_TOOL_ROUNDS + 1):
        try:
            response = client.messages.create(
                model=model, max_tokens=4096, tools=tool_definitions(), messages=history,
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                output_config={"effort": "low"},
            )
        except Exception as exc:  # anthropic.RateLimitError, APIStatusError, APIConnectionError
            log.error("agent chat request failed (%s)", type(exc).__name__)
            raise AgentUnavailable("The agent is busy right now. Try again in a minute.") from exc
        if response.stop_reason == "pause_turn":
            history.append({"role": "assistant", "content": response.content})
            continue
        if response.stop_reason != "tool_use":
            break
        history.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if getattr(block, "type", "") != "tool_use":
                continue
            text, failed = _run_tool(block.name, block.input, user, charge)
            steps.append({"tool": block.name, "input": _summary(block.input), "ok": not failed})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": text, "is_error": failed})
        history.append({"role": "user", "content": results})
    if response is None:
        raise AgentUnavailable("The agent did not respond. Try again.")
    if response.stop_reason == "refusal":
        reply = "I can't help with that request. Ask about why something in the repository is the way it is."
    else:
        reply = "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text").strip()
    if response.stop_reason == "tool_use":
        reply = (reply + "\n\n" if reply else "") + "I stopped after several lookups. Ask a narrower question to continue."
    if not reply:
        reply = "I could not find an answer in the indexed history. Try naming a file, config key or dependency."
    log.info("agent chat: %d tool calls, stop=%s", len(steps), response.stop_reason)
    return {"reply": reply, "steps": steps}

