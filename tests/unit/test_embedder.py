"""Unit tests for :class:`repolens.ingestion.embedder.CodeEmbedder`.

These use an injected fake encoder so the suite never downloads the real model. A gated
integration test that exercises the actual jina model lives in
``tests/integration/test_embedder_model.py``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from repolens.ingestion.chunker import IndexChunk, count_tokens
from repolens.ingestion.embedder import CodeEmbedder
from repolens.utils.cache import DiskCache

_DIM = 8


class FakeEncoder:
    """Deterministic encoder: maps text → vector via its SHA-256, counts calls."""

    def __init__(self, dim: int = _DIM) -> None:
        self.dim = dim
        self.encoded_texts: list[str] = []

    def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray:
        self.encoded_texts.extend(sentences)
        rows = []
        for text in sentences:
            digest = hashlib.sha256(text.encode()).digest()
            vec = np.frombuffer(digest[: self.dim], dtype=np.uint8).astype(np.float32)
            rows.append(vec / 255.0)
        return np.vstack(rows)


def _chunk(symbol: str, body: str) -> IndexChunk:
    return IndexChunk(
        file_path=f"{symbol}.py",
        symbol_name=symbol,
        symbol_type="function",
        signature=f"def {symbol}()",
        docstring="",
        body=body,
        start_line=1,
        end_line=1 + body.count("\n"),
        language="python",
        token_count=count_tokens(body),
    )


def test_embed_returns_matrix_with_one_row_per_chunk() -> None:
    embedder = CodeEmbedder(dimension=_DIM, model=FakeEncoder())
    result = embedder.embed([_chunk("f", "return 1")])
    assert result.shape == (1, _DIM)
    assert result.dtype == np.float32


def test_embed_multiple_chunks_preserves_order() -> None:
    encoder = FakeEncoder()
    embedder = CodeEmbedder(dimension=_DIM, model=encoder)
    chunks = [_chunk("a", "return 1"), _chunk("b", "return 2"), _chunk("c", "return 3")]
    result = embedder.embed(chunks)
    assert result.shape == (3, _DIM)
    # Re-encoding a single chunk yields the same row (deterministic encoder).
    single = CodeEmbedder(dimension=_DIM, model=FakeEncoder()).embed([chunks[1]])
    assert np.allclose(result[1], single[0])


def test_empty_input_returns_empty_matrix() -> None:
    embedder = CodeEmbedder(dimension=_DIM, model=FakeEncoder())
    result = embedder.embed([])
    assert result.shape == (0, _DIM)


def test_cache_hit_on_second_call(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path, namespace="embeddings")
    encoder = FakeEncoder()
    embedder = CodeEmbedder(dimension=_DIM, cache=cache, model=encoder)
    chunk = _chunk("f", "return 1")

    first = embedder.embed([chunk])
    assert len(encoder.encoded_texts) == 1  # model ran once
    assert cache.misses == 1 and cache.hits == 0

    second = embedder.embed([chunk])
    assert len(encoder.encoded_texts) == 1  # model NOT run again
    assert cache.hits == 1  # served from cache
    assert np.allclose(first, second)


def test_cache_only_embeds_misses(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path, namespace="embeddings")
    encoder = FakeEncoder()
    embedder = CodeEmbedder(dimension=_DIM, cache=cache, model=encoder)

    a, b = _chunk("a", "return 1"), _chunk("b", "return 2")
    embedder.embed([a])
    assert len(encoder.encoded_texts) == 1

    # Second batch: only the new chunk should be encoded.
    embedder.embed([a, b])
    assert len(encoder.encoded_texts) == 2  # one prior + one new miss
    assert encoder.encoded_texts[-1] == CodeEmbedder.embed_text_for(b)


def test_embed_query_returns_vector() -> None:
    embedder = CodeEmbedder(dimension=_DIM, model=FakeEncoder())
    vec = embedder.embed_query("how does routing work")
    assert vec.shape == (_DIM,)
    assert vec.dtype == np.float32
