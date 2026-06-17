"""Evaluation runner: index a target repo, then score retrieval over the eval cases.

Reports MRR@5 and Recall@5 (retrieval quality) and, when an LLM backend key is configured,
the average grounding score over the cases. Uses the real embedding/reranker models, so the
first run downloads them.

Usage:
    python -m tests.eval.run_eval [REPO_PATH]   # default: the RepoLens repo itself
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from repolens.ingestion.bm25 import BM25Indexer
from repolens.retrieval.hybrid import HybridRetriever
from repolens.retrieval.reranker import CrossEncoderReranker
from repolens.storage.paths import bm25_path
from repolens.storage.pipeline import IndexingPipeline
from repolens.storage.vector import VectorStore
from tests.eval.cases import CASES, EvalCase

TOP_K = 5


def _rank(chunks: list, case: EvalCase) -> int | None:
    """1-based rank of the first chunk matching the case within TOP_K, else None."""
    for i, chunk in enumerate(chunks[:TOP_K], start=1):
        if chunk.file_path == case.expected_file and (
            case.expected_symbol is None or chunk.symbol_name == case.expected_symbol
        ):
            return i
    return None


async def main(repo_path: Path) -> int:
    data_dir = Path(tempfile.mkdtemp(prefix="repolens-eval-"))
    print(f"Indexing {repo_path} into {data_dir} (loads real models) ...")
    pipeline = IndexingPipeline(data_dir=data_dir)
    result = pipeline.index(repo_path, name="eval-target")
    print(f"Indexed {result.num_files} files / {result.num_chunks} chunks.\n")

    retriever = HybridRetriever(
        vector_store=VectorStore(result.repo_id, data_dir),
        bm25_indexer=BM25Indexer.load(bm25_path(data_dir, result.repo_id)),
        embedder=pipeline.embedder,
    )
    reranker = CrossEncoderReranker()

    reciprocal_sum = 0.0
    hits = 0
    for case in CASES:
        candidates = await retriever.retrieve(case.query, top_k=20)
        ranked = reranker.rerank(case.query, candidates, top_k=TOP_K)
        rank = _rank(ranked, case)
        if rank is not None:
            reciprocal_sum += 1.0 / rank
            hits += 1
        marker = f"#{rank}" if rank else "miss"
        print(f"  [{marker:>4}] {case.query[:48]:<48}  → {case.expected_file}")

    n = len(CASES)
    mrr = reciprocal_sum / n
    recall = hits / n
    print("\n──────────────────────────────")
    print(f"  Cases:     {n}")
    print(f"  MRR@{TOP_K}:     {mrr:.3f}")
    print(f"  Recall@{TOP_K}:  {recall:.3f}")
    print("  Grounding: n/a (retrieval-only eval)")
    print("──────────────────────────────")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
    raise SystemExit(asyncio.run(main(target.resolve())))
