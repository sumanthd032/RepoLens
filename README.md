<div align="center">

# 🔭 RepoLens

**Ask any repository how it actually works — and get answers grounded in the real code.**

<!-- Badges (wired up in Step 10) -->
<!-- ![CI](https://img.shields.io/github/actions/workflow/status/repolens/repolens/ci.yml) -->
<!-- ![PyPI](https://img.shields.io/pypi/v/repolens) -->
<!-- ![Python](https://img.shields.io/badge/python-3.11%2B-blue) -->
<!-- ![License](https://img.shields.io/badge/license-MIT-green) -->

</div>

---

RepoLens is a **local-first RAG engine** for OSS contributors. It answers questions about any
repository using only the checked-out code — every answer sentence cites a `file:line-range`
span, every citation is re-verified against the file on disk, and a per-answer **grounding score**
tells you how well the answer is supported. It also detects where **documentation has drifted**
from the code.

## Why RepoLens

- **Grounded, not guessed.** Answers cite verifiable `file:line` spans. If the code doesn't
  contain the answer, RepoLens says so instead of hallucinating from model memory.
- **Code-native retrieval.** Source is parsed with tree-sitter into semantic units, embedded
  with a code-aware model, and retrieved with hybrid dense + BM25 search, reranking, and
  caller/callee graph expansion.
- **Doc-drift detection.** A dedicated mode flags doc claims that the code contradicts or no
  longer supports — CI-compatible with a non-zero exit on new findings.

## Quick install

> ⚠️ RepoLens is under active development. Installation will be available from PyPI once the
> first release ships (see [docs/STEPS.md](docs/STEPS.md)).

```bash
pip install repolens
```

## Quickstart

```bash
repolens index ./path/to/repo      # index a local repository
repolens ask "how does routing work?" --repo <id>
repolens drift --repo <id>         # find stale documentation
repolens serve                     # launch the web UI at http://localhost:8000
```

## Architecture

```
Browser (React)
    │  HTTP ↓   ↑ SSE
FastAPI server
    ├── Ingestion   git walker → tree-sitter → chunker → graph → embedder + BM25 → storage
    ├── Retrieval   storage → hybrid (dense + BM25) → RRF → reranker → graph expander
    ├── Generation  chunks → grounded prompt → LLM → citation validator → grounding scorer
    └── Drift       storage → claim extractor → NLI entailment → markdown report
```

Full details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Tech stack](docs/TECHSTACK.md)
- [Implementation steps](docs/STEPS.md)
- [UI specification](docs/UI_SPEC.md)
- [Contributing](CONTRIBUTING.md)

## License

[MIT](LICENSE)
