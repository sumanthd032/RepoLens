"""SQLite symbol-graph store.

:class:`GraphStore` persists a :class:`networkx.DiGraph` as a node/edge adjacency list in a
per-repo SQLite database. The retrieval graph expander (Step 6) calls
:meth:`get_neighbours` to pull a matched chunk's callers, callees, and enclosing type so they
can be retrieved alongside the primary hit.
"""

from __future__ import annotations

import sqlite3
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import networkx as nx

from repolens.storage.paths import graph_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    chunk_id TEXT PRIMARY KEY,
    symbol   TEXT,
    type     TEXT,
    file     TEXT
);
CREATE TABLE IF NOT EXISTS edges (
    src  TEXT NOT NULL,
    dst  TEXT NOT NULL,
    type TEXT NOT NULL,
    PRIMARY KEY (src, dst, type)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
"""


class GraphStore:
    """Stores and queries one repository's symbol graph."""

    def __init__(self, repo_id: str, data_dir: str | Path) -> None:
        self.repo_id = repo_id
        self.db_path = graph_db_path(data_dir, repo_id)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, graph: nx.DiGraph) -> None:
        """Replace the stored graph with ``graph`` (nodes + typed edges)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM nodes")
            conn.execute("DELETE FROM edges")
            conn.executemany(
                "INSERT INTO nodes (chunk_id, symbol, type, file) VALUES (?, ?, ?, ?)",
                [
                    (n, d.get("symbol"), d.get("type"), d.get("file"))
                    for n, d in graph.nodes(data=True)
                ],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO edges (src, dst, type) VALUES (?, ?, ?)",
                [(u, v, d.get("type", "")) for u, v, d in graph.edges(data=True)],
            )

    def load(self) -> nx.DiGraph:
        """Rebuild the stored :class:`networkx.DiGraph`."""
        graph: nx.DiGraph = nx.DiGraph()
        with self._connect() as conn:
            for row in conn.execute("SELECT chunk_id, symbol, type, file FROM nodes"):
                graph.add_node(
                    row["chunk_id"],
                    symbol=row["symbol"],
                    type=row["type"],
                    file=row["file"],
                )
            for row in conn.execute("SELECT src, dst, type FROM edges"):
                graph.add_edge(row["src"], row["dst"], type=row["type"])
        return graph

    def get_neighbours(self, chunk_id: str, hops: int = 1) -> list[str]:
        """Return chunk ids within ``hops`` of ``chunk_id`` (both edge directions).

        Treats the graph as undirected for expansion so both callers and callees of a matched
        symbol are returned. The seed id itself is excluded.
        """
        if hops < 1:
            return []
        with self._connect() as conn:
            visited = {chunk_id}
            frontier: deque[tuple[str, int]] = deque([(chunk_id, 0)])
            result: list[str] = []
            while frontier:
                node, depth = frontier.popleft()
                if depth >= hops:
                    continue
                for neighbour in self._adjacent(conn, node):
                    if neighbour not in visited:
                        visited.add(neighbour)
                        result.append(neighbour)
                        frontier.append((neighbour, depth + 1))
        return result

    @staticmethod
    def _adjacent(conn: sqlite3.Connection, node: str) -> list[str]:
        rows = conn.execute(
            "SELECT dst AS n FROM edges WHERE src=? UNION SELECT src AS n FROM edges WHERE dst=?",
            (node, node),
        ).fetchall()
        return [row["n"] for row in rows]

    def count_edges(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0])
