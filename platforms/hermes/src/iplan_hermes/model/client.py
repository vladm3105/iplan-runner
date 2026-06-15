"""Pluggable model transport. Stub is offline/deterministic; real clients are
import-guarded behind extras and are integration-only (need credentials)."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ModelResponse:
    text: str
    usage: dict[str, Any] = field(default_factory=dict)


class ModelClient(Protocol):
    def complete(self, prompt: str) -> ModelResponse: ...


class StubModelClient:
    """Returns a canned response for any prompt (offline tests / scenarios)."""

    def __init__(self, text: str = "{}", usage: dict[str, Any] | None = None) -> None:
        self._text = text
        self._usage = usage or {"tokens": 0, "cost_usd": 0.0}

    def complete(self, prompt: str) -> ModelResponse:
        return ModelResponse(text=self._text, usage=dict(self._usage))


class _AnthropicClient:
    """Best-effort real client (integration-only; needs the [anthropic] extra)."""

    def __init__(self, model: str, api_key: str) -> None:
        anthropic = importlib.import_module("anthropic")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, prompt: str) -> ModelResponse:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        usage = getattr(message, "usage", None)
        tokens = (getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)) if usage else 0
        return ModelResponse(text=message.content[0].text, usage={"tokens": tokens, "cost_usd": 0.0})


def get_model_client(provider: str, model: str, api_key: str) -> ModelClient:
    if provider == "anthropic":
        return _AnthropicClient(model, api_key)
    raise NotImplementedError(f"model provider {provider!r} not supported (integration-only)")
