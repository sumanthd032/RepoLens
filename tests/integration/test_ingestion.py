"""Integration test for the full indexing pipeline (Step 5).

Builds a tiny fake repo, runs ``IndexingPipeline`` with a fake embedder (so no model is
downloaded), and asserts every storage artefact was created and is queryable.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from repolens.ingestion.bm25 import BM25Indexer
from repolens.ingestion.embedder import CodeEmbedder
from repolens.storage.graph import GraphStore
from repolens.storage.metadata import MetadataStore
from repolens.storage.paths import bm25_path, graph_db_path, lancedb_path, metadata_db_path
from repolens.storage.pipeline import IndexingPipeline, IndexProgress
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
def pipeline(tmp_path: Path) -> IndexingPipeline:
    embedder = CodeEmbedder(dimension=_DIM, model=FakeEncoder())
    return IndexingPipeline(data_dir=tmp_path / "data", embedder=embedder)


def test_pipeline_runs_and_reports_summary(
    pipeline: IndexingPipeline, fake_repo: Path
) -> None:
    events: list[IndexProgress] = []
    result = pipeline.index(fake_repo, name="demo", on_progress=events.append)

    assert result.num_files == 3
    assert result.num_chunks > 0
    assert result.languages == ["python"]
    # Progress callback fired through the expected stages.
    stages = {e.stage for e in events}
    assert {"walk", "embed", "store", "graph", "done"} <= stages


def test_lancedb_created_and_searchable(
    pipeline: IndexingPipeline, fake_repo: Path, tmp_path: Path
) -> None:
    result = pipeline.index(fake_repo, name="demo")
    data_dir = tmp_path / "data"

    assert lancedb_path(data_dir, result.repo_id).exists()
    store = VectorStore(result.repo_id, data_dir)
    assert store.count() == result.num_chunks

    # A query vector returns chunks (order by similarity; just assert we get results back).
    query = pipeline.embedder.embed_query("handle route")
    hits = store.search(query, top_k=3)
    assert hits
    assert all(h.language == "python" for h in hits)


def test_sqlite_metadata_written(
    pipeline: IndexingPipeline, fake_repo: Path, tmp_path: Path
) -> None:
    result = pipeline.index(fake_repo, name="demo")
    data_dir = tmp_path / "data"

    assert metadata_db_path(data_dir).is_file()
    store = MetadataStore(data_dir)
    repo = store.get_repo(result.repo_id)
    assert repo is not None
    assert repo.status == "ready"
    assert repo.num_files == 3
    assert repo.num_chunks == result.num_chunks

    files = store.list_files(result.repo_id)
    assert {f.path for f in files} == {"auth.py", "router.py", "models.py"}
    assert all(len(f.content_hash) == 64 for f in files)


def test_bm25_index_persisted_and_searchable(
    pipeline: IndexingPipeline, fake_repo: Path, tmp_path: Path
) -> None:
    result = pipeline.index(fake_repo, name="demo")
    data_dir = tmp_path / "data"

    path = bm25_path(data_dir, result.repo_id)
    assert path.is_file()
    bm25 = BM25Indexer.load(path)
    hits = bm25.search("handle route", top_k=5)
    assert hits, "BM25 should return results for 'handle route'"


def test_symbol_graph_persisted_with_edges(
    pipeline: IndexingPipeline, fake_repo: Path, tmp_path: Path
) -> None:
    result = pipeline.index(fake_repo, name="demo")
    data_dir = tmp_path / "data"

    assert graph_db_path(data_dir, result.repo_id).is_file()
    store = GraphStore(result.repo_id, data_dir)
    graph = store.load()
    assert graph.number_of_nodes() == result.num_chunks
    # handle_route calls resolve → there should be at least one "calls" edge.
    calls = [d for _, _, d in graph.edges(data=True) if d["type"] == "calls"]
    assert calls

    # get_neighbours returns connected chunks for a node that has edges.
    connected = next(
        n
        for n in graph.nodes
        if list(graph.successors(n)) or list(graph.predecessors(n))
    )
    assert store.get_neighbours(connected, hops=1)


def test_reindex_is_idempotent(
    pipeline: IndexingPipeline, fake_repo: Path, tmp_path: Path
) -> None:
    first = pipeline.index(fake_repo, name="demo")
    second = pipeline.index(fake_repo, repo_id=first.repo_id, name="demo")
    data_dir = tmp_path / "data"

    # Re-indexing the same repo must not duplicate rows.
    store = VectorStore(first.repo_id, data_dir)
    assert store.count() == second.num_chunks == first.num_chunks
