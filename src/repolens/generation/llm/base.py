"""LLM client interface.

Every backend (Groq, OpenAI, Anthropic, Ollama) implements :class:`BaseLLMClient` so the rest
of the system — HyDE in retrieval, answer generation, and drift claim extraction — depends only
on this one async streaming contract and never on a specific SDK. Streaming is the primitive
because the ``/ask`` endpoint forwards tokens to the browser over SSE as they arrive.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# A chat message in the provider-neutral ``{"role": ..., "content": ...}`` shape.
Message = dict[str, str]


class BaseLLMClient(ABC):
    """Abstract async chat client. Subclasses implement :meth:`stream`."""

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    def stream(
        self, messages: list[Message], system: str | None = None
    ) -> AsyncIterator[str]:
        """Yield response text tokens for ``messages`` (optionally with a ``system`` prompt)."""
        raise NotImplementedError

    async def complete(self, messages: list[Message], system: str | None = None) -> str:
        """Convenience: consume :meth:`stream` and return the full response string."""
        return "".join([token async for token in self.stream(messages, system)])
