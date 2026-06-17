"""LLM client backends: base interface plus Groq, OpenAI, Anthropic, and Ollama clients."""

from __future__ import annotations

from typing import TYPE_CHECKING

from repolens.config import Config, get_config
from repolens.generation.llm.anthropic import AnthropicClient
from repolens.generation.llm.base import BaseLLMClient, Message
from repolens.generation.llm.ollama import OllamaClient
from repolens.generation.llm.openai import GroqClient, OpenAIClient

if TYPE_CHECKING:
    from pydantic import SecretStr

__all__ = [
    "AnthropicClient",
    "BaseLLMClient",
    "GroqClient",
    "Message",
    "OllamaClient",
    "OpenAIClient",
    "create_llm_client",
]


def _require(secret: SecretStr | None, env_var: str) -> str:
    if secret is None:
        raise ValueError(f"{env_var} is not set; required for the selected LLM backend")
    return secret.get_secret_value()


def create_llm_client(config: Config | None = None) -> BaseLLMClient:
    """Build the LLM client for the configured ``generation.llm_backend``.

    Raises :class:`ValueError` if the chosen backend needs an API key that is not configured.
    """
    config = config or get_config()
    gen = config.generation
    backend = gen.llm_backend

    if backend == "groq":
        return GroqClient(
            api_key=_require(config.groq_api_key, "GROQ_API_KEY"),
            model=gen.llm_model,
            max_tokens=gen.max_answer_tokens,
        )
    if backend == "openai":
        return OpenAIClient(
            api_key=_require(config.openai_api_key, "OPENAI_API_KEY"),
            model=gen.llm_model,
            max_tokens=gen.max_answer_tokens,
        )
    if backend == "anthropic":
        return AnthropicClient(
            api_key=_require(config.anthropic_api_key, "ANTHROPIC_API_KEY"),
            model=gen.llm_model,
            max_tokens=gen.max_answer_tokens,
        )
    if backend == "ollama":
        return OllamaClient(base_url=config.ollama_base_url, model=gen.llm_model)

    raise ValueError(f"Unknown LLM backend: {backend!r}")
