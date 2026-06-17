"""Anthropic Claude chat client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import anthropic

from repolens.generation.llm.base import BaseLLMClient, Message
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger("generation.llm.anthropic")

DEFAULT_MAX_TOKENS = 2048


class AnthropicClient(BaseLLMClient):
    """Streaming client for the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> None:
        super().__init__(model)
        self.max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def stream(
        self, messages: list[Message], system: str | None = None
    ) -> AsyncIterator[str]:
        # Anthropic takes the system prompt as a top-level arg, not a message role; omit it
        # entirely when absent rather than passing a sentinel.
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system is not None:
            kwargs["system"] = system
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
