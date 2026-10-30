"""Language-model adapters with one tiny interface. Backends: `fake` (no network; callers fall back to
template rendering), `anthropic` (Claude Haiku by default), `sarvam` (sarvam-105b through Sarvam's
OpenAI-compatible endpoint) and `openai` (any OpenAI-compatible server, e.g. Ollama, OpenRouter).

Prompts are plain strings; `complete_json` asks for a JSON object and validates it with a pydantic model.
Reasoning is disabled on Sarvam by default so the output is the answer, not a trace."""

from __future__ import annotations

import inspect
import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from untangle.config import Settings, settings

log = logging.getLogger("untangle.llm")
T = TypeVar("T", bound=BaseModel)

DEFAULT_MODELS = {"anthropic": "claude-haiku-5-5", "sarvam": "sarvam-105b", "openai": "gpt-4o-mini", "fake": "fake"}
_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


class LLMUnavailable(RuntimeError):
    """No usable backend (missing key / package / network). Callers degrade to templates."""


class LLM:
    backend = "fake"
    model = "fake"

    def complete(self, system: str, user: str, *, temperature: float = 0.1, max_tokens: int = 1024) -> str:
        raise LLMUnavailable("fake backend has no model; render from the graph instead")

    def complete_json(self, system: str, user: str, schema: type[T], *, temperature: float = 0.0, max_tokens: int = 2048) -> T:
        text = self.complete(system + "\nAnswer with one JSON object and nothing else.", user, temperature=temperature, max_tokens=max_tokens)
        return parse_json(text, schema)

    @property
    def available(self) -> bool:
        return self.backend != "fake"


class FakeLLM(LLM):
    """Deterministic stand-in. `scripted` maps a substring of the user prompt to a canned reply (tests)."""

    def __init__(self, scripted: dict[str, str] | None = None):
        self.scripted = scripted or {}
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, *, temperature: float = 0.1, max_tokens: int = 1024) -> str:
        self.calls.append((system, user))
        for needle, reply in self.scripted.items():
            if needle in user:
                return reply
        raise LLMUnavailable("fake backend has no model; render from the graph instead")


class AnthropicLLM(LLM):
    backend = "anthropic"

    def __init__(self, api_key: str, model: str):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMUnavailable("pip install anthropic (or `uv sync --extra llm`)") from exc
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def complete(self, system: str, user: str, *, temperature: float = 0.1, max_tokens: int = 1024) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user}],
        }
        # Anthropic SDK 2.x removed the top-level temperature parameter for the current Claude models. Keep
        # compatibility with older SDKs while allowing the locked production SDK to make a real request.
        parameters = inspect.signature(self.client.messages.create).parameters
        if "temperature" in parameters:
            kwargs["temperature"] = temperature
        if "thinking" in parameters:
            kwargs["thinking"] = {"type": "disabled"}
        msg = self.client.messages.create(**kwargs)
        return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text").strip()


class OpenAICompatibleLLM(LLM):
    """OpenAI chat-completions protocol. Sarvam: base_url https://api.sarvam.ai/v1, model sarvam-105b."""

    def __init__(self, api_key: str, model: str, base_url: str | None, backend: str = "openai", extra_body: dict | None = None):
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMUnavailable("pip install openai (or `uv sync --extra llm`)") from exc
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model, self.backend, self.extra_body = model, backend, extra_body or {}

    def complete(self, system: str, user: str, *, temperature: float = 0.1, max_tokens: int = 1024) -> str:
        kwargs: dict[str, Any] = {}
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body
        res = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **kwargs,
        )
        return (res.choices[0].message.content or "").strip()


def parse_json(text: str, schema: type[T]) -> T:
    """Tolerates code fences and prose around the object."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else candidate
    try:
        return schema.model_validate_json(candidate)
    except ValidationError:
        pass
    m = _JSON_BLOCK.search(candidate)
    if not m:
        raise ValueError(f"model returned no JSON object: {text[:200]!r}")
    return schema.model_validate(json.loads(m.group(0)))


def make_llm(s: Settings | None = None) -> LLM:
    s = s or settings()
    backend = s.llm_backend
    model = s.llm_model or DEFAULT_MODELS.get(backend, "")
    try:
        if backend == "anthropic" and s.anthropic_api_key:
            return AnthropicLLM(s.anthropic_api_key, model)
        if backend == "sarvam" and s.sarvam_api_key:
            # sarvam-105b reasons by default; the answer text is what we want, so turn it off.
            return OpenAICompatibleLLM(
                s.sarvam_api_key, model, "https://api.sarvam.ai/v1", backend="sarvam", extra_body={"reasoning_effort": None}
            )
        if backend == "openai" and s.openai_api_key:
            return OpenAICompatibleLLM(s.openai_api_key, model, s.openai_base_url, backend="openai")
    except LLMUnavailable as exc:
        log.warning("LLM backend %s unavailable (%s); using the fake backend", backend, exc)
    if backend != "fake":
        log.warning("LLM_BACKEND=%s but its API key is missing; answers are rendered from the graph without a model", backend)
    return FakeLLM()
