"""LLM configuration and initialization."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import os

from litellm import completion

from portfolio_chat_agent.config.settings import get_settings


class LiteLLMClient:
    def __init__(self, model: str, temperature: float = 0.0):
        self.model = model
        self.temperature = temperature

    def invoke(self, prompt: str) -> Any:
        vertex_project = os.getenv("VERTEXAI_PROJECT")
        vertex_location = os.getenv("VERTEXAI_LOCATION")
        api_base = os.getenv("OPENAI_COMPAT_API_BASE")
        api_key = os.getenv("OPENAI_COMPAT_API_KEY")
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        if self.model.startswith("vertex_ai/"):
            kwargs["vertex_project"] = vertex_project
            kwargs["vertex_location"] = vertex_location
        if self.model.startswith("openai/"):
            kwargs["api_base"] = api_base
            kwargs["api_key"] = api_key

        response = completion(**kwargs)
        content = response["choices"][0]["message"]["content"]
        return SimpleNamespace(content=content)


def get_llm(
    *, model: str | None = None, temperature: float = 0.0, provider_override: str | None = None
) -> LiteLLMClient:
    settings = get_settings()
    provider = (provider_override or settings.llm_provider).lower()
    if provider in {"openai", "gpt", "chatgpt", "litellm"}:
        selected_model = model or settings.openai_model
        if provider in {"openai", "gpt", "chatgpt"} and selected_model.startswith("openai/"):
            selected_model = selected_model.split("/", 1)[1]
        return LiteLLMClient(model=selected_model, temperature=temperature)
    if provider in {"vertex", "vertex_ai", "gemini"}:
        selected_model = model or "gemini-1.5-flash-8b"
        if not selected_model.startswith("vertex_ai/"):
            selected_model = f"vertex_ai/{selected_model}"
        return LiteLLMClient(model=selected_model, temperature=temperature)
    raise ValueError(
        f"Unsupported LLM_PROVIDER '{provider}'. "
        "Expected one of: openai, gpt, chatgpt, litellm, vertex, vertex_ai, gemini"
    )
