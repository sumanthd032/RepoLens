"""LanceDB vector store.

:class:`VectorStore` persists index chunks together with their dense embeddings in an embedded
LanceDB table (one table per repository, no server). It supports upsert (idempotent
re-indexing keyed by ``chunk_id``), dense ANN search, and id lookup — the operations the
retrieval engine needs to turn a query embedding into ranked :class:`IndexChunk` objects.
"""

from __future__ import annotations

from dataclasses import asdict, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any

import lancedb
import numpy as np

from repolens.ingestion.chunker import IndexChunk
from repolens.storage.paths import lancedb_path
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from lancedb.table import Table

logger = get_logger("storage.vector")

_TABLE = "chunks"
_VECTOR = "vector"
_ID = "chunk_id"
_CHUNK_FIELDS = [f.name for f in fields(IndexChunk)]


class VectorStore:
    """Embedded LanceDB store of chunks + embeddings for a single repository."""

    def __init__(self, repo_id: str, data_dir: str | Path, table_name: str = _TABLE) -> None:
        self.repo_id = repo_id
        self.path = lancedb_path(data_dir, repo_id)
        self.path.mkdir(parents=True, exist_ok=True)
        self.table_name = table_name
        self._db = lancedb.connect(str(self.path))

    def _table(self) -> Table | None:
        if self.table_name in self._table_names():
            return self._db.open_table(self.table_name)
        return None

    def _table_names(self) -> list[str]:
        # list_tables() may return a paginated listing object; normalise to a name list.
        listing = self._db.list_tables()
        names = getattr(listing, "tables", listing)
        return list(names)

    def upsert(self, chunks: list[IndexChunk], embeddings: np.ndarray) -> int:
        """Insert or update ``chunks`` with their ``embeddings`` (row-aligned). Returns count."""
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch"
            )
        if not chunks:
            return 0

        rows = [
            {**asdict(chunk), _VECTOR: np.asarray(vector, dtype=np.float32).tolist()}
            for chunk, vector in zip(chunks, embeddings, strict=True)
        ]
        table = self._table()
        if table is None:
            self._db.create_table(self.table_name, data=rows)
        else:
            (
                table.merge_insert(_ID)
                .when_matched_update_all()
                .when_not_matched_insert_all()
                .execute(rows)
            )
        return len(rows)

    def search(self, query_embedding: np.ndarray, top_k: int = 20) -> list[IndexChunk]:
        """Return up to ``top_k`` chunks nearest to ``query_embedding`` (closest first)."""
        table = self._table()
        if table is None:
            return []
        vector = np.asarray(query_embedding, dtype=np.float32).reshape(-1).tolist()
        rows = table.search(vector).limit(top_k).to_list()
        return [self._row_to_chunk(row) for row in rows]

    def get_by_ids(self, chunk_ids: list[str]) -> list[IndexChunk]:
        """Fetch chunks by id, preserving the order of ``chunk_ids`` (missing ids skipped)."""
        table = self._table()
        if table is None or not chunk_ids:
            return []
        quoted = ", ".join("'" + cid.replace("'", "''") + "'" for cid in chunk_ids)
        rows = table.search().where(f"{_ID} IN ({quoted})").limit(len(chunk_ids)).to_list()
        by_id = {row[_ID]: self._row_to_chunk(row) for row in rows}
        return [by_id[cid] for cid in chunk_ids if cid in by_id]

    def count(self) -> int:
        table = self._table()
        return table.count_rows() if table is not None else 0

    @staticmethod
    def _row_to_chunk(row: dict[str, Any]) -> IndexChunk:
        return IndexChunk(**{name: row[name] for name in _CHUNK_FIELDS})
