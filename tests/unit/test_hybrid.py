"""Unit tests for RRF fusion and the HybridRetriever orchestration (no models loaded)."""

from __future__ import annotations

import numpy as np

from repolens.ingestion.chunker import IndexChunk
from repolens.retrieval.hybrid import HybridRetriever, reciprocal_rank_fusion


def make_chunk(chunk_id: str) -> IndexChunk:
    return IndexChunk(
        file_path=f"{chunk_id}.py",
        symbol_name=chunk_id,
        symbol_type="function",
        signature=f"def {chunk_id}()",
        docstring="",
        body=f"def {chunk_id}(): pass",
        start_line=1,
        end_line=1,
        language="python",
        token_count=5,
        chunk_id=chunk_id,
    )


# --- reciprocal_rank_fusion ---------------------------------------------------


def test_rrf_rewards_agreement_across_lists() -> None:
    dense = ["a", "b", "c"]
    bm25 = ["b", "d", "a"]
    fused = dict(reciprocal_rank_fusion([dense, bm25], k=60))

    # "a" is rank 1 dense + rank 3 bm25; "b" is rank 2 dense + rank 1 bm25 — both beat singletons.
    assert fused["a"] > fused["c"]
    assert fused["b"] > fused["d"]
    # Every id from either list appears exactly once.
    assert set(fused) == {"a", "b", "c", "d"}


def test_rrf_orders_by_score_descending() -> None:
    fused = reciprocal_rank_fusion([["x", "y", "z"]], k=60)
    scores = [score for _, score in fused]
    assert scores == sorted(scores, reverse=True)
    assert [cid for cid, _ in fused] == ["x", "y", "z"]


def test_rrf_smaller_k_sharpens_top_rank() -> None:
    top_small = dict(reciprocal_rank_fusion([["a", "b"]], k=1))
    top_large = dict(reciprocal_rank_fusion([["a", "b"]], k=1000))
    assert top_small["a"] > top_large["a"]


# --- HybridRetriever ----------------------------------------------------------


class FakeVectorStore:
    def __init__(self, chunks: list[IndexChunk]) -> None:
        self._by_id = {c.chunk_id: c for c in chunks}

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[IndexChunk]:
        return list(self._by_id.values())[:top_k]

    def get_by_ids(self, chunk_ids: list[str]) -> list[IndexChunk]:
        return [self._by_id[cid] for cid in chunk_ids if cid in self._by_id]


class FakeBM25:
    def __init__(self, hits: list[tuple[str, float]]) -> None:
        self._hits = hits

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        return self._hits[:top_k]


class FakeEmbedder:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def embed_query(self, text: str) -> np.ndarray:
        self.seen.append(text)
        return np.zeros(4, dtype=np.float32)


class FakeLLM:
    def __init__(self, snippet: str) -> None:
        self._snippet = snippet

    async def stream(self, messages: list[dict[str, str]], system: str | None = None):
        for token in self._snippet.split():
            yield token + " "


async def test_retrieve_fuses_dense_and_bm25_and_materialises_bm25_only_ids() -> None:
    chunks = [make_chunk(c) for c in ("a", "b", "c", "d")]
    retriever = HybridRetriever(
        vector_store=FakeVectorStore(chunks),  # type: ignore[arg-type]
        bm25_indexer=FakeBM25([("d", 9.0), ("a", 1.0)]),  # type: ignore[arg-type]
        embedder=FakeEmbedder(),  # type: ignore[arg-type]
    )
    results = await retriever.retrieve("query", top_k=4)
    ids = [c.chunk_id for c in results]

    # "d" only appears in BM25 yet is returned — it was fetched via get_by_ids.
    assert "d" in ids
    assert set(ids) <= {"a", "b", "c", "d"}
    assert ids == list(dict.fromkeys(ids)), "results must be deduplicated"


async def test_retrieve_without_llm_embeds_raw_query() -> None:
    embedder = FakeEmbedder()
    retriever = HybridRetriever(
        vector_store=FakeVectorStore([make_chunk("a")]),  # type: ignore[arg-type]
        bm25_indexer=FakeBM25([]),  # type: ignore[arg-type]
        embedder=embedder,  # type: ignore[arg-type]
    )
    await retriever.retrieve("how does auth work")
    assert embedder.seen == ["how does auth work"]


async def test_retrieve_with_llm_expands_query_via_hyde() -> None:
    embedder = FakeEmbedder()
    retriever = HybridRetriever(
        vector_store=FakeVectorStore([make_chunk("a")]),  # type: ignore[arg-type]
        bm25_indexer=FakeBM25([]),  # type: ignore[arg-type]
        embedder=embedder,  # type: ignore[arg-type]
        llm_client=FakeLLM("def authenticate(user): ..."),
    )
    await retriever.retrieve("how does auth work")
    embedded = embedder.seen[0]
    assert embedded.startswith("how does auth work")
    assert "authenticate" in embedded, "HyDE snippet should be appended to the query"


async def test_hyde_failure_falls_back_to_raw_query() -> None:
    class BrokenLLM:
        async def stream(self, messages: list[dict[str, str]], system: str | None = None):
            raise RuntimeError("backend down")
            yield  # pragma: no cover - makes this an async generator

    embedder = FakeEmbedder()
    retriever = HybridRetriever(
        vector_store=FakeVectorStore([make_chunk("a")]),  # type: ignore[arg-type]
        bm25_indexer=FakeBM25([]),  # type: ignore[arg-type]
        embedder=embedder,  # type: ignore[arg-type]
        llm_client=BrokenLLM(),
    )
    results = await retriever.retrieve("how does auth work")
    assert embedder.seen == ["how does auth work"]  # fell back, no snippet appended
    assert [c.chunk_id for c in results] == ["a"]


def test_rrf_empty_input_is_empty() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []
