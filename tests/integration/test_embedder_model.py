"""Integration test for the real jina embedding model.

Skipped unless ``REPOLENS_RUN_MODEL_TESTS=1`` (the model is a large one-time download and
needs sentence-transformers + torch). Verifies the Step-4 definition of done: a single chunk
embeds to a ``(1, 768)`` matrix and the cache is used on the second call.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from repolens.ingestion.chunker import IndexChunk, count_tokens
from repolens.ingestion.embedder import DEFAULT_DIMENSION, CodeEmbedder
from repolens.utils.cache import DiskCache

pytestmark = pytest.mark.skipif(
    os.environ.get("REPOLENS_RUN_MODEL_TESTS") != "1",
    reason="set REPOLENS_RUN_MODEL_TESTS=1 to run the real embedding-model test",
)


def _chunk() -> IndexChunk:
    body = "def add(a, b):\n    return a + b"
    return IndexChunk(
        file_path="m.py",
        symbol_name="add",
        symbol_type="function",
        signature="def add(a, b)",
        docstring="Add two numbers.",
        body=body,
        start_line=1,
        end_line=2,
        language="python",
        token_count=count_tokens(body),
    )


def test_real_model_shape_and_cache(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path, namespace="embeddings")
    embedder = CodeEmbedder(cache=cache, device="cpu")

    first = embedder.embed([_chunk()])
    assert first.shape == (1, DEFAULT_DIMENSION)
    assert first.dtype == np.float32
    assert cache.misses == 1

    second = embedder.embed([_chunk()])
    assert cache.hits == 1
    assert np.allclose(first, second)
