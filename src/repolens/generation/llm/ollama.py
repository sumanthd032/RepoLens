"""Ollama local chat client.

Talks to a local Ollama server's ``/api/chat`` endpoint over HTTP. This is the fully-offline
backend: no API key, no network calls leave the machine — useful for air-gapped use and for the
"all data is local" guarantee when a user does not want to send code to a hosted LLM.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx

from repolens.generation.llm.base import BaseLLMClient, Message
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger("generation.llm.ollama")


class OllamaClient(BaseLLMClient):
    """Streaming client for a local Ollama server."""

    def __init__(self, base_url: str, model: str) -> None:
        super().__init__(model)
        self.base_url = base_url.rstrip("/")

    async def stream(
        self, messages: list[Message], system: str | None = None
    ) -> AsyncIterator[str]:
        payload: list[Message] = list(messages)
        if system:
            payload = [{"role": "system", "content": system}, *payload]
        body = {"model": self.model, "messages": payload, "stream": True}
        async with (
            httpx.AsyncClient(timeout=None) as client,
            client.stream("POST", f"{self.base_url}/api/chat", json=body) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                data = json.loads(line)
                token = data.get("message", {}).get("content")
                if token:
                    yield token
                if data.get("done"):
                    break
