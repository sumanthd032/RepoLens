"""Symbol-graph expander.

Retrieval and reranking find the chunks that *match* a query, but understanding code often
requires its neighbourhood: the functions a matched function calls, and the ones that call it.
:class:`GraphExpander` pulls those 1-hop neighbours from the Step-5 symbol graph and fetches
their chunks from the vector store, so the generator sees callers and callees alongside the
primary hits. The result is deduplicated and capped so expansion never floods the prompt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from repolens.ingestion.chunker import IndexChunk
    from repolens.storage.graph import GraphStore
    from repolens.storage.vector import VectorStore

logger = get_logger("retrieval.expander")

DEFAULT_MAX_TOTAL = 12


class GraphExpander:
    """Augments retrieved chunks with their graph neighbours (callers/callees)."""

    def __init__(self, graph_store: GraphStore, vector_store: VectorStore) -> None:
        self.graph_store = graph_store
        self.vector_store = vector_store

    def expand(
        self,
        chunks: list[IndexChunk],
        hops: int = 1,
        max_total: int = DEFAULT_MAX_TOTAL,
    ) -> list[IndexChunk]:
        """Return ``chunks`` followed by their neighbours, deduplicated and capped.

        The original chunks always come first and are never dropped; neighbour chunks fill the
        remaining slots up to ``max_total`` (in graph-traversal order). With ``hops < 1`` or no
        room left, the input is returned unchanged (truncated to ``max_total``).
        """
        result = list(chunks[:max_total])
        seen = {c.chunk_id for c in result}
        if hops < 1 or len(result) >= max_total:
            return result

        neighbour_ids: list[str] = []
        for chunk in chunks:
            for neighbour_id in self.graph_store.get_neighbours(chunk.chunk_id, hops=hops):
                if neighbour_id not in seen:
                    seen.add(neighbour_id)
                    neighbour_ids.append(neighbour_id)

        if not neighbour_ids:
            return result

        room = max_total - len(result)
        added = self.vector_store.get_by_ids(neighbour_ids[:room])
        result.extend(added)
        logger.debug("Graph expansion added %d neighbour chunks", len(added))
        return result
