"""The built-in agent: tool loop, limits and failure handling, with a scripted model client."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from untangle import agent_chat, mcp_server
from untangle.auth.service import User

USER = User(id="user:t", email="t@auth.test", name="T", role="member", created_at=0)


class Script:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def text(value, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=value)])


def tool_use(name, args, id_="t1"):
    return SimpleNamespace(stop_reason="tool_use", content=[SimpleNamespace(type="tool_use", id=id_, name=name, input=args)])


@pytest.fixture
def fake_tools(monkeypatch):
    monkeypatch.setitem(mcp_server.TOOLS["list_repositories"], "fn", lambda args, user: ("knadh/listmonk: 18 decisions", {}))
    monkeypatch.setitem(mcp_server.TOOLS["search_repository"], "fn", lambda args, user: (_ for _ in ()).throw(mcp_server.ToolError("No such repository.")))


def test_read_only_tools_exclude_graph_writes():
    names = {t["name"] for t in agent_chat.tool_definitions()}
    assert "remember_decision" not in names and {"ask_why", "list_decisions", "who_to_ask"} <= names


def test_tool_loop_runs_tools_and_returns_the_final_answer(fake_tools):
    client = Script(tool_use("list_repositories", {}), text("listmonk is indexed."))
    charged = []
    result = agent_chat.chat([{"role": "user", "content": "What is indexed?"}], "knadh/listmonk", USER, charge=charged.append, client=client)
    assert result == {"reply": "listmonk is indexed.", "steps": [{"tool": "list_repositories", "input": "", "ok": True}]}
    assert charged == ["read"]
    second = client.calls[1]["messages"]
    assert second[0]["content"].startswith("[Selected repository: knadh/listmonk]")
    assert second[-1]["content"][0] == {"type": "tool_result", "tool_use_id": "t1", "content": "knadh/listmonk: 18 decisions", "is_error": False}
    assert client.calls[0]["output_config"] == {"effort": "low"}


def test_tool_errors_go_back_to_the_model(fake_tools):
    client = Script(tool_use("search_repository", {"repo": "x/y", "query": "retry"}), text("That repository is not indexed."))
    result = agent_chat.chat([{"role": "user", "content": "find retry"}], None, USER, charge=lambda kind: None, client=client)
    assert result["steps"] == [{"tool": "search_repository", "input": "retry", "ok": False}]
    assert client.calls[1]["messages"][-1]["content"][0]["is_error"] is True


def test_write_tool_requests_are_refused(fake_tools):
    client = Script(tool_use("remember_decision", {"repo": "x/y", "subject": "a", "decision": "b"}), text("ok"))
    result = agent_chat.chat([{"role": "user", "content": "remember this"}], None, USER, charge=lambda kind: None, client=client)
    assert result["steps"][0]["ok"] is False


def test_limits_stop_the_loop(fake_tools):
    def limited(kind):
        raise agent_chat.AgentLimit("slow down", 30)

    with pytest.raises(agent_chat.AgentLimit):
        agent_chat.chat([{"role": "user", "content": "q"}], None, USER, charge=limited, client=Script(tool_use("list_repositories", {}), text("x")))


def test_history_must_end_with_a_question_and_is_trimmed():
    with pytest.raises(ValueError):
        agent_chat._history([{"role": "assistant", "content": "hi"}], None)
    long = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(31)]
    history = agent_chat._history(long, None)
    assert len(history) <= agent_chat.MAX_TURNS and history[0]["role"] == "user" and history[-1]["content"] == "m30"


def test_refusals_and_model_failures_have_plain_messages(fake_tools):
    refused = agent_chat.chat([{"role": "user", "content": "q"}], None, USER, charge=lambda kind: None,
                              client=Script(SimpleNamespace(stop_reason="refusal", content=[])))
    assert "can't help" in refused["reply"]

    class Broken:
        messages = SimpleNamespace(create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("upstream secret")))

    with pytest.raises(agent_chat.AgentUnavailable) as error:
        agent_chat.chat([{"role": "user", "content": "q"}], None, USER, charge=lambda kind: None, client=Broken())
    assert "secret" not in str(error.value)
