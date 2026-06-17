"""OpenAI-compatible chat clients.

:class:`OpenAIClient` talks to any OpenAI-compatible Chat Completions endpoint. Because Groq's
hosted API is OpenAI-compatible, :class:`GroqClient` is just this client pointed at Groq's base
URL — which is why Groq can be the free default backend without a second SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import openai

from repolens.generation.llm.base import BaseLLMClient, Message
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from openai import AsyncStream
    from openai.types.chat import ChatCompletionChunk

logger = get_logger("generation.llm.openai")

DEFAULT_MAX_TOKENS = 2048


class OpenAIClient(BaseLLMClient):
    """Streaming client for OpenAI's (or any compatible) Chat Completions API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        super().__init__(model)
        self.max_tokens = max_tokens
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def stream(
        self, messages: list[Message], system: str | None = None
    ) -> AsyncIterator[str]:
        payload: list[Message] = list(messages)
        if system:
            payload = [{"role": "system", "content": system}, *payload]
        stream = cast(
            "AsyncStream[ChatCompletionChunk]",
            await self._client.chat.completions.create(
                model=self.model,
                messages=payload,  # type: ignore[arg-type]
                stream=True,
                max_tokens=self.max_tokens,
            ),
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class GroqClient(OpenAIClient):
    """OpenAI-compatible client for Groq's free hosted inference (default backend)."""

    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self, api_key: str, model: str, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> None:
        super().__init__(api_key, model, base_url=self.BASE_URL, max_tokens=max_tokens)
