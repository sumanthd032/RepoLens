"""Code embedder.

:class:`CodeEmbedder` turns index chunks into dense vectors using the local
``jinaai/jina-embeddings-v2-base-code`` model (loaded via sentence-transformers — no network
call beyond the one-time model download). Embeddings are content-addressed in the Step-2
:class:`~repolens.utils.cache.DiskCache`: a chunk is only run through the model when the hash
of its embed-text is not already cached, so re-indexing an unchanged repo is nearly free.

The model is loaded lazily on first use and can be injected for testing, keeping unit tests
free of the heavyweight download.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import numpy as np

from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from repolens.ingestion.chunker import IndexChunk
    from repolens.utils.cache import DiskCache

logger = get_logger("ingestion.embedder")

DEFAULT_MODEL = "jinaai/jina-embeddings-v2-base-code"
DEFAULT_DIMENSION = 768
# ALiBi attention allocates a (batch x heads x seq x seq) tensor, so peak memory scales with
# batch_size * max_seq_length**2. With a 1024-token cap, batch_size=8 keeps the forward pass
# well under a few GB on CPU; 32 could exceed 4 GB and trigger the OOM killer.
_BATCH_SIZE = 8

# jina-v2-base-code defaults to max_seq_length=8192 and uses ALiBi dense attention, whose
# memory cost is quadratic in sequence length. A chunk that is small by the chunker's regex
# token count but large in BPE subwords (e.g. one unbroken string/data blob) would otherwise
# allocate tens of GB on CPU. Capping the sequence length truncates such inputs and keeps
# embedding memory bounded. The cap sits above the 512-token chunk budget to leave headroom
# for BPE expansion of normal code.
_MAX_SEQ_LENGTH = 1024


class _EncoderModel(Protocol):
    """Minimal interface the embedder needs from a SentenceTransformer-like model."""

    def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray: ...


class CodeEmbedder:
    """Embeds index chunks into a ``(N, dimension)`` float32 matrix, with disk caching.

    Args:
        model_name: HuggingFace model id loaded via sentence-transformers.
        cache: Optional :class:`DiskCache` for per-chunk embedding reuse.
        dimension: Embedding dimension (used to assemble empty results / validate).
        device: Torch device string (``"cpu"``, ``"cuda"``); ``None`` lets the model decide.
        model: Pre-built encoder (injected in tests to avoid loading the real model).
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        cache: DiskCache | None = None,
        dimension: int = DEFAULT_DIMENSION,
        device: str | None = None,
        model: _EncoderModel | None = None,
    ) -> None:
        self.model_name = model_name
        self.cache = cache
        self.dimension = dimension
        self.device = device
        self._model = model

    @property
    def model(self) -> _EncoderModel:
        """Lazily load and cache the SentenceTransformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model %s", self.model_name)
            model = SentenceTransformer(
                self.model_name,
                device=self.device,
                trust_remote_code=True,
            )
            # Bound the attention window so a pathologically long chunk cannot exhaust RAM.
            current = getattr(model, "max_seq_length", None)
            if current is None or current > _MAX_SEQ_LENGTH:
                model.max_seq_length = _MAX_SEQ_LENGTH
            self._model = model
        return self._model

    @staticmethod
    def embed_text_for(chunk: IndexChunk) -> str:
        """Compose the text embedded for a chunk: symbol, signature, docstring, body."""
        parts = [chunk.symbol_name, chunk.signature, chunk.docstring, chunk.body]
        return "\n".join(p for p in parts if p)

    def _cache_key(self, text: str) -> str:
        # Namespacing by model keeps vectors from different models from colliding.
        from repolens.utils.cache import DiskCache

        return DiskCache.make_key(f"{self.model_name}\n{text}")

    def embed(self, chunks: list[IndexChunk]) -> np.ndarray:
        """Embed ``chunks`` and return a ``(len(chunks), dimension)`` float32 array.

        Cached chunks are served from disk; only cache misses are run through the model, in
        batches of 32. Row order matches the input order.
        """
        if not chunks:
            return np.empty((0, self.dimension), dtype=np.float32)

        texts = [self.embed_text_for(c) for c in chunks]
        keys = [self._cache_key(t) for t in texts]
        vectors: list[np.ndarray | None] = [None] * len(chunks)

        miss_indices: list[int] = []
        for i, key in enumerate(keys):
            cached = self.cache.get(key) if self.cache is not None else None
            if cached is not None:
                vectors[i] = np.asarray(cached, dtype=np.float32)
            else:
                miss_indices.append(i)

        if miss_indices:
            miss_texts = [texts[i] for i in miss_indices]
            encoded = self._encode(miss_texts)
            for pos, i in enumerate(miss_indices):
                vector = np.asarray(encoded[pos], dtype=np.float32)
                vectors[i] = vector
                if self.cache is not None:
                    self.cache.set(keys[i], vector)

        return np.vstack([v for v in vectors if v is not None]).astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string into a ``(dimension,)`` float32 vector."""
        row: np.ndarray = self._encode([query])[0]
        return np.asarray(row, dtype=np.float32)

    def _encode(self, texts: list[str]) -> np.ndarray:
        result = self.model.encode(
            texts,
            batch_size=_BATCH_SIZE,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return np.asarray(result, dtype=np.float32)
