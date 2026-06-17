"""Integration test for the retrieval engine (Step 6).

Indexes a tiny fake repo with the real Step-5 pipeline (using a deterministic fake embedder so
no model is downloaded), then runs hybrid retrieval → cross-encoder rerank (fake) → graph
expansion against the persisted stores and asserts each stage behaves.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from repolens.ingestion.bm25 import BM25Indexer
from repolens.ingestion.chunker import IndexChunk
from repolens.ingestion.embedder import CodeEmbedder
from repolens.retrieval.expander import GraphExpander
from repolens.retrieval.hybrid import HybridRetriever
from repolens.retrieval.reranker import CrossEncoderReranker, chunk_preview
from repolens.storage.graph import GraphStore
from repolens.storage.paths import bm25_path
from repolens.storage.pipeline import IndexingPipeline
from repolens.storage.vector import VectorStore

_DIM = 16


class FakeEncoder:
    """Deterministic encoder mapping text → a fixed-size vector via its hash."""

    def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray:
        rows = []
        for text in sentences:
            digest = hashlib.sha256(text.encode()).digest()
            vec = np.frombuffer(digest[:_DIM], dtype=np.uint8).astype(np.float32)
            rows.append(vec / 255.0)
        return np.vstack(rows)


class FakeCrossEncoder:
    """Scores a (query, text) pair by counting query-token occurrences in the text."""

    def predict(self, sentences: list[list[str]], **kwargs: object) -> list[float]:
        scores = []
        for query, text in sentences:
            terms = query.lower().split()
            low = text.lower()
            scores.append(float(sum(low.count(term) for term in terms)))
        return scores


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    files = {
        "auth.py": (
            "def hash_password(pw):\n"
            "    return _digest(pw)\n\n\n"
            "def _digest(value):\n"
            "    return value[::-1]\n"
        ),
        "router.py": (
            "def handle_route(path):\n"
            '    """Dispatch an incoming route."""\n'
            "    return resolve(path)\n\n\n"
            "def resolve(path):\n"
            "    return path.strip('/')\n"
        ),
        "models.py": (
            "class User:\n"
            "    def __init__(self, name):\n"
            "        self.name = name\n\n"
            "    def greet(self):\n"
            "        return hash_password(self.name)\n"
        ),
    }
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return repo


@pytest.fixture
def indexed(tmp_path: Path, fake_repo: Path) -> tuple[str, Path, CodeEmbedder]:
    embedder = CodeEmbedder(dimension=_DIM, model=FakeEncoder())
    data_dir = tmp_path / "data"
    pipeline = IndexingPipeline(data_dir=data_dir, embedder=embedder)
    result = pipeline.index(fake_repo, name="demo")
    return result.repo_id, data_dir, embedder


def make_retriever(repo_id: str, data_dir: Path, embedder: CodeEmbedder) -> HybridRetriever:
    return HybridRetriever(
        vector_store=VectorStore(repo_id, data_dir),
        bm25_indexer=BM25Indexer.load(bm25_path(data_dir, repo_id)),
        embedder=embedder,
    )


async def test_hybrid_retrieve_finds_relevant_chunk(
    indexed: tuple[str, Path, CodeEmbedder],
) -> None:
    repo_id, data_dir, embedder = indexed
    retriever = make_retriever(repo_id, data_dir, embedder)

    results = await retriever.retrieve("handle route", top_k=8)
    assert results
    symbols = {c.symbol_name for c in results}
    # BM25's camelCase/snake_case tokeniser matches "handle route" → handle_route.
    assert "handle_route" in symbols


def test_reranker_orders_by_relevance(
    indexed: tuple[str, Path, CodeEmbedder],
) -> None:
    repo_id, data_dir, _ = indexed
    store = VectorStore(repo_id, data_dir)
    chunks = store.search(np.zeros(_DIM, dtype=np.float32), top_k=20)

    reranker = CrossEncoderReranker(model=FakeCrossEncoder())
    ranked = reranker.rerank("hash_password", chunks, top_k=3)

    assert len(ranked) <= 3
    # The chunk whose preview contains "hash_password" most often ranks first.
    top = ranked[0]
    assert "hash_password" in chunk_preview(top)


def test_graph_expander_adds_callee(
    indexed: tuple[str, Path, CodeEmbedder],
) -> None:
    repo_id, data_dir, _ = indexed
    store = VectorStore(repo_id, data_dir)
    graph_store = GraphStore(repo_id, data_dir)

    all_chunks = store.search(np.zeros(_DIM, dtype=np.float32), top_k=20)
    handle = next(c for c in all_chunks if c.symbol_name == "handle_route")

    expander = GraphExpander(graph_store, store)
    expanded = expander.expand([handle], hops=1)

    symbols = {c.symbol_name for c in expanded}
    # handle_route calls resolve → expansion should pull resolve in alongside it.
    assert "handle_route" in symbols
    assert "resolve" in symbols


def test_graph_expander_caps_total(
    indexed: tuple[str, Path, CodeEmbedder],
) -> None:
    repo_id, data_dir, _ = indexed
    store = VectorStore(repo_id, data_dir)
    graph_store = GraphStore(repo_id, data_dir)
    chunks: list[IndexChunk] = store.search(np.zeros(_DIM, dtype=np.float32), top_k=20)

    expander = GraphExpander(graph_store, store)
    expanded = expander.expand(chunks, hops=1, max_total=2)
    assert len(expanded) == 2
