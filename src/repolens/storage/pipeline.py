"""Indexing pipeline.

:class:`IndexingPipeline` ties the whole index-time flow together::

    walker → parser → chunker → symbol graph
                              ↘ embedder → vector store
                              ↘ BM25 index
           → metadata store (repo + per-file stats)

It is the single entry point the CLI (``repolens index``) and the API (``POST /api/repos``)
call to index a repository. An optional progress callback makes it drivable by the SSE
progress endpoint added in Step 8.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from git import GitError, Repo

from repolens.config import Config, get_config
from repolens.ingestion.bm25 import BM25Indexer
from repolens.ingestion.chunker import IndexChunk, SemanticChunker
from repolens.ingestion.embedder import CodeEmbedder
from repolens.ingestion.graph import SymbolGraphBuilder
from repolens.ingestion.parser import TreeSitterParser
from repolens.ingestion.walker import GitWalker
from repolens.storage.graph import GraphStore
from repolens.storage.metadata import MetadataStore
from repolens.storage.paths import bm25_path, embedding_cache_dir
from repolens.storage.vector import VectorStore
from repolens.utils.cache import DiskCache
from repolens.utils.logger import get_logger

logger = get_logger("storage.pipeline")


@dataclass
class IndexProgress:
    """A progress update emitted during indexing."""

    stage: str  # "walk" | "embed" | "store" | "graph" | "done"
    message: str = ""
    current: int = 0
    total: int = 0


@dataclass
class IndexResult:
    """Summary returned after indexing completes."""

    repo_id: str
    name: str
    num_files: int
    num_chunks: int
    languages: list[str]
    head_sha: str | None


ProgressCallback = Callable[[IndexProgress], None]


class IndexingPipeline:
    """Runs and persists the full ingestion pipeline for a repository."""

    def __init__(
        self,
        data_dir: str | Path | None = None,
        config: Config | None = None,
        embedder: CodeEmbedder | None = None,
    ) -> None:
        self.config = config or get_config()
        self.data_dir = Path(data_dir).expanduser() if data_dir else self.config.data_dir
        self.metadata = MetadataStore(self.data_dir)
        self.parser = TreeSitterParser()
        self.chunker = SemanticChunker(
            max_tokens=self.config.index.max_chunk_tokens,
            overlap_tokens=self.config.index.chunk_overlap_tokens,
        )
        self._embedder = embedder

    @property
    def embedder(self) -> CodeEmbedder:
        if self._embedder is None:
            self._embedder = CodeEmbedder(
                model_name=self.config.index.embedding_model,
                cache=DiskCache(embedding_cache_dir(self.data_dir), namespace="embeddings"),
            )
        return self._embedder

    def index(
        self,
        repo_path: str | Path,
        repo_id: str | None = None,
        name: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> IndexResult:
        """Index ``repo_path`` end to end, persisting all artefacts to disk."""
        root = Path(repo_path).expanduser().resolve()
        repo_id = repo_id or str(uuid.uuid4())
        name = name or root.name
        progress = on_progress or (lambda _e: None)

        self.metadata.upsert_repo(repo_id, name, str(root), status="indexing")
        try:
            return self._run(root, repo_id, name, progress)
        except Exception as exc:
            logger.exception("Indexing failed for %s", root)
            self.metadata.update_status(repo_id, "error", error=str(exc))
            raise

    def _run(self, root: Path, repo_id: str, name: str, progress: ProgressCallback) -> IndexResult:
        languages = set(self.config.index.languages)
        walker = GitWalker(root, languages=languages)

        all_chunks: list[IndexChunk] = []
        file_stats: list[tuple[str, str, int, str]] = []  # (path, language, n_chunks, hash)
        seen_languages: set[str] = set()

        progress(IndexProgress(stage="walk", message="Scanning repository"))
        for walked in walker.walk():
            parsed = self.parser.parse(walked.path, walked.content, walked.language)
            chunks = self.chunker.chunk_all(parsed)
            all_chunks.extend(chunks)
            seen_languages.add(walked.language)
            content_hash = hashlib.sha256(walked.content.encode("utf-8")).hexdigest()
            file_stats.append((walked.path, walked.language, len(chunks), content_hash))
            progress(IndexProgress(stage="walk", message=walked.path, current=len(file_stats)))

        if not all_chunks:
            logger.warning("No indexable chunks found in %s", root)
            self.metadata.update_stats(repo_id, len(file_stats), 0, sorted(seen_languages))
            self.metadata.update_status(repo_id, "ready")
            return IndexResult(repo_id, name, len(file_stats), 0, sorted(seen_languages), None)

        # Embed + persist vectors.
        progress(IndexProgress(stage="embed", message="Embedding chunks", total=len(all_chunks)))
        embeddings = self.embedder.embed(all_chunks)
        progress(IndexProgress(stage="store", message="Writing vector store"))
        VectorStore(repo_id, self.data_dir).upsert(all_chunks, embeddings)

        # BM25 index.
        bm25 = BM25Indexer()
        bm25.build(all_chunks)
        bm25.save(bm25_path(self.data_dir, repo_id))

        # Symbol graph.
        progress(IndexProgress(stage="graph", message="Building symbol graph"))
        graph = SymbolGraphBuilder().build(all_chunks)
        GraphStore(repo_id, self.data_dir).save(graph)

        # File-level metadata.
        for path, language, n_chunks, content_hash in file_stats:
            self.metadata.upsert_file(repo_id, path, language, n_chunks, content_hash)

        head_sha = self._head_sha(root)
        languages_sorted = sorted(seen_languages)
        self.metadata.update_stats(
            repo_id, len(file_stats), len(all_chunks), languages_sorted, head_sha
        )
        self.metadata.update_status(repo_id, "ready")

        progress(IndexProgress(stage="done", message="Indexing complete", total=len(all_chunks)))
        logger.info(
            "Indexed %s: %d files, %d chunks, %d graph edges",
            name,
            len(file_stats),
            len(all_chunks),
            graph.number_of_edges(),
        )
        return IndexResult(
            repo_id, name, len(file_stats), len(all_chunks), languages_sorted, head_sha
        )

    @staticmethod
    def _head_sha(root: Path) -> str | None:
        try:
            return Repo(root).head.commit.hexsha
        except (GitError, ValueError):
            return None
