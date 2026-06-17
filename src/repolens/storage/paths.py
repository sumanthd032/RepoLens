"""On-disk layout for RepoLens data.

Everything lives under ``data_dir`` (default ``~/.repolens``). Per-repo artefacts are grouped
under ``repos/<repo_id>/`` so a repo can be deleted by removing one directory::

    <data_dir>/
      metadata.db                 # SQLite: repos + files tables (all repos)
      cache/embeddings/           # DiskCache: content-addressed embedding vectors
      repos/<repo_id>/
        lancedb/                  # LanceDB vector table
        bm25.pkl                  # serialised BM25 index
        graph.db                  # SQLite adjacency list for the symbol graph
"""

from __future__ import annotations

from pathlib import Path


def data_root(data_dir: str | Path) -> Path:
    return Path(data_dir).expanduser()


def metadata_db_path(data_dir: str | Path) -> Path:
    return data_root(data_dir) / "metadata.db"


def embedding_cache_dir(data_dir: str | Path) -> Path:
    return data_root(data_dir) / "cache"


def repo_dir(data_dir: str | Path, repo_id: str) -> Path:
    return data_root(data_dir) / "repos" / repo_id


def lancedb_path(data_dir: str | Path, repo_id: str) -> Path:
    return repo_dir(data_dir, repo_id) / "lancedb"


def bm25_path(data_dir: str | Path, repo_id: str) -> Path:
    return repo_dir(data_dir, repo_id) / "bm25.pkl"


def graph_db_path(data_dir: str | Path, repo_id: str) -> Path:
    return repo_dir(data_dir, repo_id) / "graph.db"
