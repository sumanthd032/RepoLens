"""Evaluation cases: 20 (query, expected_file, expected_symbol) tuples.

These target RepoLens's own source so ``scripts/eval.sh`` can self-evaluate retrieval quality
without an external corpus. A case is a hit when a top-k result is from ``expected_file`` and (if
given) carries ``expected_symbol``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalCase:
    query: str
    expected_file: str
    expected_symbol: str | None = None


CASES: list[EvalCase] = [
    EvalCase(
        "how are citations validated against the source file",
        "src/repolens/generation/validator.py",
        "CitationValidator",
    ),
    EvalCase(
        "how is the NLI grounding score computed for an answer",
        "src/repolens/generation/scorer.py",
        "GroundingScorer",
    ),
    EvalCase(
        "how does hybrid retrieval fuse dense and bm25 results",
        "src/repolens/retrieval/hybrid.py",
        "HybridRetriever",
    ),
    EvalCase(
        "reciprocal rank fusion of ranked lists",
        "src/repolens/retrieval/hybrid.py",
        "reciprocal_rank_fusion",
    ),
    EvalCase(
        "cross encoder reranking of candidate chunks",
        "src/repolens/retrieval/reranker.py",
        "CrossEncoderReranker",
    ),
    EvalCase(
        "expand retrieval with caller and callee neighbours",
        "src/repolens/retrieval/expander.py",
        "GraphExpander",
    ),
    EvalCase(
        "embed code chunks with caching",
        "src/repolens/ingestion/embedder.py",
        "CodeEmbedder",
    ),
    EvalCase(
        "bm25 keyword index with camelCase tokenizer",
        "src/repolens/ingestion/bm25.py",
        "BM25Indexer",
    ),
    EvalCase(
        "parse source into functions and classes with tree-sitter",
        "src/repolens/ingestion/parser.py",
        "TreeSitterParser",
    ),
    EvalCase(
        "sub-chunk large functions with a sliding window",
        "src/repolens/ingestion/chunker.py",
        "SemanticChunker",
    ),
    EvalCase(
        "walk repository files applying the ignore filter",
        "src/repolens/ingestion/walker.py",
        "GitWalker",
    ),
    EvalCase(
        "build the symbol call graph from chunks",
        "src/repolens/ingestion/graph.py",
        "SymbolGraphBuilder",
    ),
    EvalCase(
        "upsert and search vectors in lancedb",
        "src/repolens/storage/vector.py",
        "VectorStore",
    ),
    EvalCase(
        "sqlite metadata store for repositories and files",
        "src/repolens/storage/metadata.py",
        "MetadataStore",
    ),
    EvalCase(
        "persist the symbol graph adjacency list",
        "src/repolens/storage/graph.py",
        "GraphStore",
    ),
    EvalCase(
        "wire the full indexing pipeline end to end",
        "src/repolens/storage/pipeline.py",
        "IndexingPipeline",
    ),
    EvalCase(
        "extract factual claims from documentation",
        "src/repolens/drift/extractor.py",
        "ClaimExtractor",
    ),
    EvalCase(
        "classify a doc claim as supported or contradicted by code",
        "src/repolens/drift/checker.py",
        "DriftChecker",
    ),
    EvalCase(
        "build the grounded system prompt that forces citations",
        "src/repolens/generation/prompt.py",
        "build_system_prompt",
    ),
    EvalCase(
        "stream tokens from the anthropic claude backend",
        "src/repolens/generation/llm/anthropic.py",
        "AnthropicClient",
    ),
]
