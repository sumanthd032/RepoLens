# RepoLens

**Ask any repository how it actually works — and get answers grounded in the real code.**

RepoLens is a local-first RAG engine for OSS contributors. It answers questions about any
repository using only the checked-out code: every answer sentence cites a `file:line-range`
span, every citation is re-verified against the file on disk, and a per-answer **grounding
score** tells you how well the answer is supported. A dedicated mode detects where
**documentation has drifted** from the code.

## Three pillars

1. **Grounding enforcement** — verifiable citations, citation validation, and an NLI-based
   grounding score on every answer. No answers from model memory.
2. **Code-native retrieval** — tree-sitter semantic chunking, a code-aware embedding model,
   hybrid dense + BM25 search with RRF fusion, cross-encoder reranking, and caller/callee
   graph expansion.
3. **Doc-drift detection** — extracts factual claims from docs and checks each against the
   code with NLI entailment: supported, contradicted, or not found.

## Where to next

- [Quickstart](quickstart.md) — install, index a repo, ask a question, run a drift check.
- [Architecture](https://github.com/repolens/repolens/blob/main/docs/ARCHITECTURE.md)
- [Implementation steps](https://github.com/repolens/repolens/blob/main/docs/STEPS.md)
