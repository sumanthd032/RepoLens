# Changelog

All notable changes to RepoLens are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1]

### Fixed
- LLM backend failures (missing API key, provider rate-limits such as Groq 429) now surface as
  a structured `error` event on the ask stream (`rate_limited` / `llm_unconfigured` /
  `llm_error`) and a `502` with a clear message on the drift endpoint, instead of an unhandled
  500 with a stack trace.

## [0.1.0]

### Added
- Monorepo scaffolding, configuration, and tooling.
- Ingestion: git walker, tree-sitter parser, semantic chunker, symbol graph, code embedder,
  BM25 indexer.
- Storage: LanceDB vector store, SQLite metadata store, symbol-graph store, and the wired
  end-to-end indexing pipeline.
- Retrieval: HyDE hybrid (dense + BM25) search with RRF fusion, cross-encoder reranking, and
  caller/callee graph expansion.
- Generation: Groq / OpenAI / Anthropic / Ollama backends, the grounded prompt, citation
  validator, and NLI grounding scorer.
- Drift detection: claim extractor, NLI checker, and markdown/JSON reporter with a `--ci` mode.
- FastAPI server with SSE endpoints, a typer CLI (`index` / `ask` / `drift` / `serve`), and the
  Observatory web UI (streaming chat, grounding ring, drift report).
- CI/CD workflows, multi-stage Docker build, documentation, and an evaluation harness.

[Unreleased]: https://github.com/sumanthd032/repolens/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sumanthd032/repolens/releases/tag/v0.1.0
