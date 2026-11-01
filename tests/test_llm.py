"""Exercise the Claude adapter through the installed SDK's HTTP boundary."""

import json

import httpx2
from anthropic import Anthropic

from untangle.llm import AnthropicLLM


def test_claude_sdk_request_reaches_http_and_reserves_budget_for_text():
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["thinking"] == {"type": "disabled"}
        assert body["max_tokens"] == 600
        return httpx2.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
            "content": [{"type": "text", "text": "A grounded answer."}],
            "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 4},
        })

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as http:
        llm = AnthropicLLM("test-key", "claude-haiku-5-5")
        llm.client.close()
        llm.client = Anthropic(api_key="test-key", http_client=http)
        assert llm.complete("Use only evidence.", "Question and evidence", temperature=0.2, max_tokens=600) == "A grounded answer."
    assert len(requests) == 1


def test_answer_outage_falls_back_without_automatic_retry_delay():
    import pytest
    from anthropic import APIStatusError

    requests = []

    def unavailable(request):
        requests.append(request)
        return httpx2.Response(503, json={"error": {"type": "api_error", "message": "Unavailable"}})

    llm = AnthropicLLM("test-key", "claude-haiku-5-5", interactive=True)
    with httpx2.Client(transport=httpx2.MockTransport(unavailable)) as http:
        llm.client = llm.client.with_options(http_client=http)
        with pytest.raises(APIStatusError):
            llm.complete("Evidence only", "Question")
    assert len(requests) == 1
    assert requests[0].extensions["timeout"]["read"] <= 25


def test_batch_extraction_retains_retry_and_longer_response_budget():
    from pydantic import BaseModel

    class Extraction(BaseModel):
        reason: str

    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx2.Response(503, json={"error": {"type": "api_error", "message": "Unavailable"}})
        return httpx2.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
            "content": [{"type": "text", "text": '{"reason":"Documented decision"}'}],
            "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 4},
        })

    llm = AnthropicLLM("test-key", "claude-haiku-5-5")
    with httpx2.Client(transport=httpx2.MockTransport(handler)) as http:
        llm.client = llm.client.with_options(http_client=http)
        assert llm.complete_json("Extract", "Repository evidence", Extraction).reason == "Documented decision"
    assert len(requests) == 2
    assert requests[0].extensions["timeout"]["read"] > 20
