"""Cross-encoder reranker.

Hybrid retrieval (RRF over dense + BM25) is fast but coarse: it scores the query and each chunk
independently. :class:`CrossEncoderReranker` refines the shortlist by feeding each
``(query, chunk)`` pair *together* through a cross-encoder (``ms-marco-MiniLM-L-6-v2``), which
attends across both texts and gives a far better relevance estimate. It is the precision stage:
it reorders the ~20 hybrid candidates and keeps the top ``k`` (default 8) for generation.

The model is loaded lazily and can be injected for testing, keeping unit tests off the download.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from repolens.ingestion.chunker import IndexChunk

logger = get_logger("retrieval.reranker")

DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# Cap on the chunk text shown to the cross-encoder; its context window is small and the leading
# lines (signature + docstring + start of body) carry the relevance signal.
_MAX_CHARS = 2000


class _CrossEncoderModel(Protocol):
    """Minimal interface the reranker needs from a CrossEncoder-like model."""

    def predict(self, sentences: list[list[str]], **kwargs: object) -> Sequence[float]: ...


def chunk_preview(chunk: IndexChunk, max_chars: int = _MAX_CHARS) -> str:
    """Compose the text shown to the reranker: location + symbol + signature + body head."""
    header = f"{chunk.file_path} {chunk.symbol_name} {chunk.signature}".strip()
    text = f"{header}\n{chunk.body}" if chunk.body else header
    return text[:max_chars]


class CrossEncoderReranker:
    """Reorders candidate chunks by cross-encoder relevance to the query.

    Args:
        model_name: HuggingFace cross-encoder id loaded via sentence-transformers.
        device: Torch device string; ``None`` lets the model decide.
        model: Pre-built cross-encoder (injected in tests to avoid the model download).
        max_chars: Max characters of chunk text scored per pair.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str | None = None,
        model: _CrossEncoderModel | None = None,
        max_chars: int = _MAX_CHARS,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.max_chars = max_chars
        self._model = model

    @property
    def model(self) -> _CrossEncoderModel:
        """Lazily load and cache the CrossEncoder model."""
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading reranker model %s", self.model_name)
            self._model = CrossEncoder(self.model_name, device=self.device)
        return self._model

    def rerank(self, query: str, chunks: list[IndexChunk], top_k: int = 8) -> list[IndexChunk]:
        """Return the ``top_k`` chunks most relevant to ``query``, best first."""
        if not chunks:
            return []
        pairs = [[query, chunk_preview(c, self.max_chars)] for c in chunks]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(chunks, scores, strict=True), key=lambda p: p[1], reverse=True)
        return [chunk for chunk, _ in ranked[:top_k]]
