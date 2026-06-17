"""Hybrid retrieval: HyDE + dense ANN + BM25, fused with Reciprocal Rank Fusion.

:class:`HybridRetriever` is the first stage of query-time retrieval. It optionally runs **HyDE**
(Hypothetical Document Embeddings): an LLM drafts a short snippet of the code that *would* answer
the query, which is embedded instead of the bare question so the dense vector lands nearer real
implementations. Dense ANN search (over the LanceDB vectors) and BM25 keyword search run in
parallel; their ranked lists are merged with **RRF** so a chunk ranked highly by *either* signal
surfaces, without needing the two scores to be on a comparable scale.

The LLM client is optional and only typed structurally (:class:`HyDEClient`) so this module does
not depend on the Step-7 generation package; when no client is supplied the raw query is embedded.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from repolens.config import Config, get_config
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    import numpy as np

    from repolens.ingestion.bm25 import BM25Indexer
    from repolens.ingestion.chunker import IndexChunk
    from repolens.ingestion.embedder import CodeEmbedder
    from repolens.storage.vector import VectorStore

logger = get_logger("retrieval.hybrid")

DEFAULT_RRF_K = 60

_HYDE_SYSTEM = (
    "You are a code search assistant. Given a question about a codebase, write a short, "
    "plausible code snippet (with a one-line comment) that would answer it. Output only code, "
    "no prose, no markdown fences. If unsure, write a representative function signature."
)
_HYDE_USER = "Question: {query}\n\nWrite the code snippet that would answer this:"


@runtime_checkable
class HyDEClient(Protocol):
    """Minimal async LLM interface needed for HyDE (satisfied by Step-7 ``BaseLLMClient``)."""

    def stream(
        self, messages: list[dict[str, str]], system: str | None = None
    ) -> AsyncIterator[str]: ...


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[str]], k: int = DEFAULT_RRF_K
) -> list[tuple[str, float]]:
    """Fuse ranked id lists into one ``(id, score)`` ranking via RRF.

    Each list contributes ``1 / (k + rank)`` to an id's score, with ``rank`` starting at 1.
    Ids present in multiple lists accumulate score, so agreement across signals wins. Returns
    all fused ids sorted by descending score.
    """
    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


class HybridRetriever:
    """Dense + BM25 retrieval fused with RRF, with optional HyDE query expansion.

    Args:
        vector_store: LanceDB store for dense ANN search and id lookup.
        bm25_indexer: Loaded BM25 index for keyword search.
        embedder: Embeds the (optionally HyDE-expanded) query.
        llm_client: Optional async LLM used for HyDE; ``None`` embeds the raw query.
        config: Retrieval settings (``top_k_dense`` / ``top_k_bm25``); defaults to global config.
        rrf_k: RRF constant; larger values flatten the contribution of top ranks.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_indexer: BM25Indexer,
        embedder: CodeEmbedder,
        llm_client: HyDEClient | None = None,
        config: Config | None = None,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        self.vector_store = vector_store
        self.bm25 = bm25_indexer
        self.embedder = embedder
        self.llm_client = llm_client
        self.config = config or get_config()
        self.rrf_k = rrf_k

    async def retrieve(self, query: str, top_k: int = 20) -> list[IndexChunk]:
        """Return up to ``top_k`` chunks for ``query``, ranked by RRF over dense + BM25."""
        query_vector = await self._query_vector(query)

        retrieval = self.config.retrieval
        dense_chunks, bm25_hits = await asyncio.gather(
            asyncio.to_thread(self.vector_store.search, query_vector, retrieval.top_k_dense),
            asyncio.to_thread(self.bm25.search, query, retrieval.top_k_bm25),
        )

        fused = reciprocal_rank_fusion(
            [[c.chunk_id for c in dense_chunks], [cid for cid, _ in bm25_hits]],
            k=self.rrf_k,
        )
        top_ids = [chunk_id for chunk_id, _ in fused[:top_k]]
        return self._materialise(top_ids, dense_chunks)

    def _materialise(self, chunk_ids: list[str], known: list[IndexChunk]) -> list[IndexChunk]:
        """Resolve ``chunk_ids`` to chunks, reusing ``known`` and fetching the rest by id."""
        by_id = {chunk.chunk_id: chunk for chunk in known}
        missing = [cid for cid in chunk_ids if cid not in by_id]
        if missing:
            for chunk in self.vector_store.get_by_ids(missing):
                by_id[chunk.chunk_id] = chunk
        return [by_id[cid] for cid in chunk_ids if cid in by_id]

    async def _query_vector(self, query: str) -> np.ndarray:
        """Embed the query, expanding it with a HyDE snippet when an LLM is configured."""
        text = query
        if self.llm_client is not None:
            hypothetical = await self._hyde(query)
            if hypothetical:
                text = f"{query}\n{hypothetical}"
        return await asyncio.to_thread(self.embedder.embed_query, text)

    async def _hyde(self, query: str) -> str:
        """Generate a hypothetical answer snippet; return ``""`` if generation fails."""
        assert self.llm_client is not None
        messages = [{"role": "user", "content": _HYDE_USER.format(query=query)}]
        try:
            parts = [token async for token in self.llm_client.stream(messages, _HYDE_SYSTEM)]
        except Exception:
            logger.warning("HyDE generation failed; falling back to raw query", exc_info=True)
            return ""
        return "".join(parts).strip()
