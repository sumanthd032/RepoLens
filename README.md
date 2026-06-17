<div align="center">

# RepoLens

**Ask any repository how it actually works — and get answers grounded in the real code.**

[![CI](https://img.shields.io/github/actions/workflow/status/sumanthd032/repolens/ci.yml?branch=main&label=CI)](https://github.com/sumanthd032/repolens/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/repolens)](https://pypi.org/project/repolens-rag/)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

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

```bash
pip install repolens-rag
export GROQ_API_KEY=gsk_...         # free key: https://console.groq.com/keys
```

Or run it fully containerised:

```bash
GROQ_API_KEY=gsk_... docker compose up   # then open http://localhost:8000
```

## Quickstart

```bash
repolens index ./path/to/repo      # index a local repository
repolens ask "how does routing work?" --repo <id>
repolens drift --repo <id>         # find stale documentation
repolens serve                     # launch the web UI at http://localhost:8000
```

See the [Quickstart guide](docs/quickstart.md) for the full walkthrough.

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

- [Quickstart](docs/quickstart.md)
- [Configuration](docs/configuration.md)
- [API reference](docs/api-reference.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Tech stack](docs/TECHSTACK.md)
- [Contributing](CONTRIBUTING.md)

## License

[MIT](LICENSE)
