"""BM25 keyword index.

:class:`BM25Indexer` provides the exact-match half of RepoLens's hybrid retrieval. It
tokenises each chunk (symbol name + signature + body) with a code-aware tokenizer that
decomposes ``camelCase`` and ``snake_case`` identifiers — so a query for ``"handle route"``
matches a ``handleRoute`` function — builds a :class:`~rank_bm25.BM25Okapi` index, and
serialises everything to disk for reuse at query time.
"""

from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import TYPE_CHECKING

from rank_bm25 import BM25Okapi

from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from repolens.ingestion.chunker import IndexChunk

logger = get_logger("ingestion.bm25")

# Splits an identifier run into camelCase / digit components:
#   "HTTPServer" -> ["HTTP", "Server"], "parseURL2" -> ["parse", "URL", "2"]
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize_code(text: str) -> list[str]:
    """Tokenise code/text into lowercase subword tokens (camelCase + snake_case aware)."""
    tokens: list[str] = []
    for word in _WORD_RE.findall(text):
        for part in word.split("_"):
            if not part:
                continue
            for piece in _CAMEL_RE.findall(part):
                tokens.append(piece.lower())
    return tokens


class BM25Indexer:
    """Builds, queries, and persists a BM25 keyword index over index chunks."""

    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._chunk_ids: list[str] = []

    @property
    def chunk_ids(self) -> list[str]:
        return list(self._chunk_ids)

    @property
    def size(self) -> int:
        return len(self._chunk_ids)

    @staticmethod
    def _index_text(chunk: IndexChunk) -> str:
        """The text indexed for a chunk: symbol name + signature + body."""
        return f"{chunk.symbol_name}\n{chunk.signature}\n{chunk.body}"

    def build(self, chunks: list[IndexChunk]) -> None:
        """Tokenise and index ``chunks``. Replaces any previously built index."""
        self._chunk_ids = [c.chunk_id for c in chunks]
        corpus = [tokenize_code(self._index_text(c)) for c in chunks]
        if not corpus:
            self._bm25 = None
            logger.warning("BM25Indexer.build called with no chunks")
            return
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        """Return up to ``top_k`` ``(chunk_id, score)`` pairs, highest score first.

        Chunks with a non-positive BM25 score (no shared terms) are omitted.
        """
        if self._bm25 is None or not self._chunk_ids:
            return []
        tokens = tokenize_code(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(
            zip(self._chunk_ids, scores, strict=True),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return [(cid, float(score)) for cid, score in ranked[:top_k] if score > 0.0]

    def save(self, path: str | Path) -> Path:
        """Persist the index to ``path`` (pickle). Returns the written path."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"bm25": self._bm25, "chunk_ids": self._chunk_ids}
        tmp = target.with_suffix(target.suffix + ".tmp")
        with tmp.open("wb") as fh:
            pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(target)
        return target

    @classmethod
    def load(cls, path: str | Path) -> BM25Indexer:
        """Load an index previously written by :meth:`save`."""
        with Path(path).open("rb") as fh:
            payload = pickle.load(fh)
        indexer = cls()
        indexer._bm25 = payload["bm25"]
        indexer._chunk_ids = payload["chunk_ids"]
        return indexer
