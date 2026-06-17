"""Application engine: shared state and the ask/drift orchestration.

This module wires the Step 6–7 retrieval and generation pieces into the two end-to-end flows the
product exposes — answering a question and detecting documentation drift — as async generators of
SSE-shaped events. Keeping the orchestration here (rather than inside route handlers) lets the
FastAPI endpoints and the typer CLI share exactly the same logic, and lets tests drive it with
injected fake models instead of downloading the real ones.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from repolens.config import Config, get_config
from repolens.drift.checker import DriftChecker
from repolens.drift.extractor import ClaimExtractor
from repolens.drift.reporter import DriftReporter
from repolens.generation.llm import create_llm_client
from repolens.generation.prompt import (
    NOT_FOUND_MARKER,
    build_system_prompt,
    build_user_message,
)
from repolens.generation.scorer import GroundingScorer
from repolens.generation.validator import CitationValidator, parse_citations
from repolens.ingestion.bm25 import BM25Indexer
from repolens.ingestion.embedder import CodeEmbedder
from repolens.retrieval.expander import GraphExpander
from repolens.retrieval.hybrid import HybridRetriever
from repolens.retrieval.reranker import CrossEncoderReranker
from repolens.storage.graph import GraphStore
from repolens.storage.metadata import MetadataStore, RepoRecord
from repolens.storage.paths import bm25_path, embedding_cache_dir
from repolens.storage.pipeline import IndexingPipeline
from repolens.storage.vector import VectorStore
from repolens.utils.cache import DiskCache
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from repolens.generation.llm.base import BaseLLMClient
    from repolens.ingestion.chunker import IndexChunk

logger = get_logger("api.engine")

LLMFactory = Callable[[], "BaseLLMClient"]
# Splits an answer into output tokens (a word plus its trailing whitespace) for SSE streaming.
_TOKEN_RE = re.compile(r"\S+\s*")


def sse(event: str, data: dict[str, Any]) -> dict[str, str]:
    """Build an sse-starlette event payload."""
    return {"event": event, "data": json.dumps(data)}


@dataclass
class AppState:
    """Process-wide shared state: config, stores, and (heavy) models loaded once."""

    config: Config
    metadata: MetadataStore
    pipeline: IndexingPipeline
    embedder: CodeEmbedder
    reranker: CrossEncoderReranker
    scorer: GroundingScorer
    llm_factory: LLMFactory
    drift_reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    index_queues: dict[str, asyncio.Queue[dict[str, Any]]] = field(default_factory=dict)

    @property
    def data_dir(self) -> Any:
        return self.config.data_dir

    def build_retriever(
        self, repo_id: str, llm_client: BaseLLMClient | None = None
    ) -> HybridRetriever:
        return HybridRetriever(
            vector_store=VectorStore(repo_id, self.data_dir),
            bm25_indexer=BM25Indexer.load(bm25_path(self.data_dir, repo_id)),
            embedder=self.embedder,
            llm_client=llm_client,
            config=self.config,
        )

    def build_expander(self, repo_id: str) -> GraphExpander:
        return GraphExpander(
            GraphStore(repo_id, self.data_dir), VectorStore(repo_id, self.data_dir)
        )


def build_state(
    config: Config | None = None,
    *,
    embedder: CodeEmbedder | None = None,
    reranker: CrossEncoderReranker | None = None,
    scorer: GroundingScorer | None = None,
    llm_factory: LLMFactory | None = None,
) -> AppState:
    """Construct an :class:`AppState`, defaulting to real (lazily-loaded) models."""
    config = config or get_config()
    embedder = embedder or CodeEmbedder(
        model_name=config.index.embedding_model,
        cache=DiskCache(embedding_cache_dir(config.data_dir), namespace="embeddings"),
    )
    reranker = reranker or CrossEncoderReranker()
    scorer = scorer or GroundingScorer()
    llm_factory = llm_factory or (lambda: create_llm_client(config))
    return AppState(
        config=config,
        metadata=MetadataStore(config.data_dir),
        pipeline=IndexingPipeline(data_dir=config.data_dir, config=config, embedder=embedder),
        embedder=embedder,
        reranker=reranker,
        scorer=scorer,
        llm_factory=llm_factory,
    )


def _match_symbol(file: str, start: int, chunks: list[IndexChunk]) -> str | None:
    """Find the symbol of the chunk a citation falls within, for the citation event."""
    for chunk in chunks:
        if chunk.file_path == file and chunk.start_line <= start <= chunk.end_line:
            return chunk.symbol_name or None
    return None


def _cited_premises(citations: list[Any], chunks: list[IndexChunk]) -> list[str]:
    """Collect the bodies of chunks referenced by citations (fallback: all chunks)."""
    premises: list[str] = []
    for chunk in chunks:
        for cit in citations:
            if chunk.file_path == cit.file and chunk.start_line <= cit.start <= chunk.end_line:
                premises.append(chunk.body)
                break
    return premises or [c.body for c in chunks]


async def answer_events(
    state: AppState, repo: RepoRecord, query: str
) -> AsyncIterator[dict[str, str]]:
    """Yield SSE events answering ``query`` against ``repo``: token/citation/grounding/done/error.

    Generation is buffered and validated *before* any token is emitted, so an answer with a bad
    citation is regenerated (up to ``max_retries``) rather than shown — enforcing Invariant 2.
    """
    llm = state.llm_factory()
    retrieval = state.config.retrieval
    retriever = state.build_retriever(repo.id, llm_client=llm)

    chunks = await retriever.retrieve(query, top_k=retrieval.top_k_dense)
    if chunks:
        chunks = await asyncio.to_thread(
            state.reranker.rerank, query, chunks, retrieval.top_k_rerank
        )
        chunks = state.build_expander(repo.id).expand(chunks, hops=retrieval.graph_expansion_hops)
    if not chunks:
        yield sse(
            "error",
            {"message": "No relevant code found in this repository.", "type": "not_found"},
        )
        return

    system = build_system_prompt()
    user = build_user_message(query, chunks)
    validator = CitationValidator(repo.source)

    answer = ""
    validated = False
    reason = "validation failed"
    for _attempt in range(state.config.generation.max_retries + 1):
        answer = await llm.complete([{"role": "user", "content": user}], system)
        if answer.strip().startswith(NOT_FOUND_MARKER):
            yield sse("error", {"message": "Not found in this codebase.", "type": "not_found"})
            return
        result = validator.validate(answer, parse_citations(answer))
        if result.ok:
            validated = True
            break
        reason = result.reason

    if not validated:
        yield sse("error", {"message": reason, "type": "validation_failed"})
        return

    citations = parse_citations(answer)
    for token in _TOKEN_RE.findall(answer):
        yield sse("token", {"text": token})
    for cit in citations:
        yield sse(
            "citation",
            {
                "file": cit.file,
                "start": cit.start,
                "end": cit.end,
                "symbol": _match_symbol(cit.file, cit.start, chunks),
            },
        )
    grounding = await asyncio.to_thread(
        state.scorer.score, answer, _cited_premises(citations, chunks)
    )
    yield sse("grounding", {"score": round(grounding.score, 4), "verdict": grounding.verdict})
    yield sse("done", {"total_citations": len(citations)})


async def run_drift(state: AppState, repo: RepoRecord) -> DriftReporter:
    """Run the full drift detection for ``repo`` and cache the report on ``state``."""
    llm = state.llm_factory()
    claims = await ClaimExtractor(llm).extract_repo(repo.source)
    checker = DriftChecker(
        state.build_retriever(repo.id), state.scorer, top_k=state.config.retrieval.top_k_rerank
    )
    findings = await checker.check_all(claims)
    reporter = DriftReporter(findings, repo_name=repo.name)
    state.drift_reports[repo.id] = reporter.to_json()
    return reporter


async def drift_events(state: AppState, repo: RepoRecord) -> AsyncIterator[dict[str, str]]:
    """Yield SSE progress events while detecting drift, ending with the full report."""
    llm = state.llm_factory()
    yield sse("progress", {"stage": "extract", "message": "Extracting documentation claims"})
    claims = await ClaimExtractor(llm).extract_repo(repo.source)

    checker = DriftChecker(
        state.build_retriever(repo.id), state.scorer, top_k=state.config.retrieval.top_k_rerank
    )
    yield sse("progress", {"stage": "check", "message": "Checking claims", "total": len(claims)})
    findings = []
    for i, claim in enumerate(claims, start=1):
        findings.append(await checker.check(claim))
        yield sse("progress", {"stage": "check", "current": i, "total": len(claims)})

    reporter = DriftReporter(findings, repo_name=repo.name)
    state.drift_reports[repo.id] = reporter.to_json()
    yield sse("done", reporter.to_json())
