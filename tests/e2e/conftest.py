"""Shared fixtures for e2e API tests: fake models + an indexed demo repo, no downloads."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np

from repolens.api.engine import AppState, build_state
from repolens.config import Config
from repolens.generation.llm.base import BaseLLMClient, Message
from repolens.generation.scorer import GroundingScorer
from repolens.ingestion.embedder import CodeEmbedder
from repolens.retrieval.reranker import CrossEncoderReranker

_DIM = 16
_WORD = re.compile(r"[A-Za-z_]+")


class FakeEncoder:
    """Deterministic hash encoder → fixed-size vectors (no model download)."""

    def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray:
        rows = []
        for text in sentences:
            digest = hashlib.sha256(text.encode()).digest()
            rows.append(np.frombuffer(digest[:_DIM], dtype=np.uint8).astype(np.float32) / 255.0)
        return np.vstack(rows)


class FakeCrossEncoder:
    """Reranker stand-in: scores a pair by query-token occurrences in the candidate."""

    def predict(self, sentences: list[list[str]], **kwargs: object) -> list[float]:
        out = []
        for query, text in sentences:
            terms = query.lower().split()
            out.append(float(sum(text.lower().count(t) for t in terms)))
        return out


class FakeNLI:
    """NLI stand-in: entailment rises with premise/hypothesis word overlap."""

    def predict(self, sentences: list[list[str]], **kwargs: object) -> list[list[float]]:
        out = []
        for premise, hypothesis in sentences:
            p = {w.lower() for w in _WORD.findall(premise)}
            h = {w.lower() for w in _WORD.findall(hypothesis)}
            entail = round(len(p & h) / len(h), 4) if h else 0.0
            rest = (1.0 - entail) / 2
            out.append([rest, entail, rest])  # contradiction, entailment, neutral
        return out


class FakeLLM(BaseLLMClient):
    """Returns a fixed string for any prompt (used for both answers and claim JSON)."""

    def __init__(self, text: str) -> None:
        super().__init__("fake")
        self.text = text

    async def stream(self, messages: list[Message], system: str | None = None):  # type: ignore[override]
        yield self.text


def make_state(tmp_path: Path, llm_text: str) -> AppState:
    config = Config(data_dir=tmp_path / "data")  # type: ignore[call-arg]
    return build_state(
        config,
        embedder=CodeEmbedder(dimension=_DIM, model=FakeEncoder()),
        reranker=CrossEncoderReranker(model=FakeCrossEncoder()),
        scorer=GroundingScorer(model=FakeNLI()),
        llm_factory=lambda: FakeLLM(llm_text),
    )


def write_demo_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "router.py").write_text(
        "def handle_route(path):\n"
        "    return resolve(path)\n"
        "\n"
        "\n"
        "def resolve(path):\n"
        "    return path.strip('/')\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text(
        "# Demo\n\nThe handle_route function returns resolve of the path.\n",
        encoding="utf-8",
    )
    return repo


def index_demo(state: AppState, tmp_path: Path) -> str:
    """Index the demo repo and return its ready repo id."""
    repo = write_demo_repo(tmp_path)
    result = state.pipeline.index(repo, name="demo")
    return result.repo_id


async def collect_sse(
    client: object, method: str, url: str, **kwargs: object
) -> list[tuple[str, dict]]:
    """POST/GET an SSE endpoint and return the (event, data) pairs received."""
    events: list[tuple[str, dict]] = []
    async with client.stream(method, url, **kwargs) as response:  # type: ignore[attr-defined]
        assert response.status_code == 200, await response.aread()
        event = "message"
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                events.append((event, json.loads(line[len("data:") :].strip())))
    return events
