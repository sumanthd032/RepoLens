# Tech Stack — RepoLens

Every technology choice is deliberate. This document explains what, why, and what version.

---

## Python Backend

### Language — Python 3.11+
The entire ML/NLP ecosystem (sentence-transformers, LanceDB, tree-sitter bindings, FastAPI) is
Python-first. Using anything else for the backend would mean writing FFI wrappers or living
without the best tools. Python 3.11 specifically for `tomllib` (stdlib TOML parser, used for
`.repolens.toml`), structural pattern matching, and significant performance improvements over 3.10.

### Package manager — uv
Modern, Rust-based Python package manager. 10–100× faster than pip. Drop-in replacement.
Lockfile (`uv.lock`) for reproducible installs. Use `uv sync` to install all deps.

### Build backend — hatchling
Modern, PEP 517-compliant build backend. Supports `src/` layout natively. Zero configuration
needed for simple packages. Declared in `pyproject.toml` `[build-system]`.

---

## Web Framework

### FastAPI + uvicorn[standard]
FastAPI is chosen for:
- Native async support (needed for SSE streaming without blocking)
- Automatic OpenAPI docs at `/docs` (useful for frontend development)
- `BackgroundTasks` for running indexing without blocking the HTTP response
- Pydantic integration for request/response validation
- `uvicorn[standard]` includes `websockets` and `httptools` for production performance

Version: `fastapi>=0.111.0`, `uvicorn[standard]>=0.30.0`

### sse-starlette
Provides `EventSourceResponse` for clean SSE streaming with FastAPI. Handles connection
keep-alive, client disconnect detection, and event formatting automatically.

Version: `sse-starlette>=2.1.0`

---

## CLI

### typer + rich
`typer` provides a modern, type-annotated CLI builder with automatic `--help` generation and
argument validation. `rich` provides progress bars, coloured output, tables, and pretty error
formatting in the terminal.

The CLI is a thin wrapper over the same logic that the FastAPI server uses. `repolens index`
calls the ingestion pipeline directly; `repolens serve` starts FastAPI.

Version: `typer>=0.12.0`, `rich>=13.7.0`

---

## Configuration

### pydantic-settings
Loads configuration from three sources in priority order:
1. Environment variables (highest priority)
2. `.env` file
3. `.repolens.toml` project config (lowest priority)

All settings are typed and validated. Documented in `docs/configuration.md`.

Version: `pydantic>=2.7.0`, `pydantic-settings>=2.3.0`

---

## Git Operations

### GitPython
Used for:
- File discovery (`repo.git.ls_files()`)
- Reading commit SHA (`repo.head.commit.hexsha`)
- Computing incremental diff (`repo.git.diff("--name-only", old_sha, "HEAD")`)
- Cloning remote repositories (`git.Repo.clone_from(url, path)`)

Alternative considered: `pygit2` (libgit2 bindings). GitPython is simpler and sufficient for
these operations.

Version: `GitPython>=3.1.43`

---

## Code Parsing

### tree-sitter (Python bindings)
tree-sitter is the industry standard for language-aware code parsing. It produces concrete syntax
trees (CSTs) for 100+ languages via language-specific grammar packages. The Python bindings
(`tree-sitter>=0.21`) provide a stable API across all grammar packages.

**Why not regex or heuristic splitting?**
Regex breaks on multi-line strings, nested braces, and language-specific edge cases. tree-sitter
produces a proper AST so we can extract exactly the node types we want (function_definition,
class_definition, etc.) with correct start/end byte positions.

Grammar packages used (individual packages, not the monolithic `tree-sitter-languages`):
```
tree-sitter-python>=0.21.0
tree-sitter-go>=0.21.0
tree-sitter-javascript>=0.21.0
tree-sitter-typescript>=0.21.0
tree-sitter-rust>=0.21.0
tree-sitter-c>=0.21.0
tree-sitter-cpp>=0.21.0
tree-sitter-java>=0.21.0
```

Language detection: by file extension (`.py` → python, `.go` → go, etc.)

---

## Embeddings

### Model — jinaai/jina-embeddings-v2-base-code
Chosen over general-purpose embedding models because:
- **Code-aware**: trained on both code and natural language, understands symbol names, API calls,
  type signatures
- **8192 token context**: can embed a 200-line function without truncation (most models max at
  512 tokens)
- **768 dimensions**: compact enough for fast ANN search, expressive enough for high recall
- **Free and local**: no API call needed for embedding; runs on CPU

Alternatives considered:
- `text-embedding-3-small` (OpenAI): requires API call per chunk; expensive at index time
- `BAAI/bge-small-en-v1.5`: general purpose, good but not code-aware
- `microsoft/graphcodebert-base`: code-specific but only 512 tokens

Loaded via `sentence-transformers`. All embeddings cached on disk.

Version: `sentence-transformers>=3.0.0`, `torch>=2.3.0`

---

## Vector Store

### LanceDB
Chosen because it is:
- **Embedded** (no server process) — critical for a local-first developer tool
- **Columnar** (Lance format) — efficient for batch writes at index time
- **Hybrid search** built-in — supports vector search + metadata filters in one call
- **Persistent** — data survives process restarts without any configuration

Alternatives:
- **ChromaDB**: also embedded, simpler API, but slower at scale and less feature-rich
- **Qdrant**: excellent hybrid search, but requires a server (or embedded mode that is newer
  and less stable)
- **FAISS**: fast but not persistent by default; no metadata support

Version: `lancedb>=0.10.0`

---

## Keyword Search

### rank_bm25
Pure Python BM25Okapi implementation. Zero dependencies. For mid-size repos (< 100k files),
the BM25 index fits comfortably in memory and search is fast enough.

Upgrade path: `tantivy-py` (Rust-based, 100× faster) if performance becomes a bottleneck on
very large repos.

Version: `rank-bm25>=0.2.2`

---

## Symbol Graph

### NetworkX
Directed graph for caller/callee relationships, import edges, interface implementations.
Stored in SQLite as an adjacency list; loaded into NetworkX for traversal during retrieval.

NetworkX is overkill for simple 1-hop expansion, but provides a clean API and makes future
features (cycle detection, community detection, pagerank-based ranking) trivial to add.

Version: `networkx>=3.3`

---

## Reranker

### cross-encoder/ms-marco-MiniLM-L-6-v2
Cross-encoders score `(query, document)` pairs jointly (unlike bi-encoders which encode
separately). This produces much higher-quality relevance scores at the cost of being slower.

This model is a distilled, efficient cross-encoder trained on the MS MARCO passage ranking
dataset. At ~22M parameters, it runs fast on CPU.

Used at step 2 of retrieval: after RRF fusion of dense + BM25 results (fast), before passing
chunks to the LLM context window (expensive).

---

## Grounding Scorer / NLI

### cross-encoder/nli-deberta-v3-small
DeBERTa-v3-small fine-tuned for Natural Language Inference. Input: (premise, hypothesis).
Output: `entailment | neutral | contradiction` with confidence scores.

Used in two places:
1. **Grounding scorer**: premise = cited code chunk, hypothesis = answer sentence
2. **Drift checker**: premise = retrieved code, hypothesis = doc claim

At ~44M parameters, runs on CPU in < 100ms per pair. Small enough to load alongside the
embedding model without exceeding typical laptop RAM.

---

## LLM Backends

### Primary — Anthropic Claude (anthropic SDK)
Default backend. Claude follows complex structured instructions well, including the citation
format requirement. Use `claude-sonnet-4-5` as default (balance of quality and speed).

### Alternative — OpenAI (openai SDK)
For users who prefer GPT-4 or GPT-4o.

### Local — Ollama (httpx)
For fully offline / private repo usage. Calls the Ollama REST API directly via `httpx`.
Any Ollama-compatible model works; `codellama:13b` or `deepseek-coder` recommended.

---

## Frontend

### React 18 + TypeScript
Industry standard. `useTransition` and concurrent features available for smooth streaming.
TypeScript ensures the API contract between frontend and backend is type-safe.

### Vite
Fast build tool. Dev server with hot module replacement. Native ESM. `vite.config.ts` includes
a proxy rule: all `/api/*` requests in dev mode are proxied to `localhost:8000`.

### Tailwind CSS v3
Utility-first CSS. Configured in `tailwind.config.ts` with the Observatory custom palette
(see `docs/UI_SPEC.md`). Tailwind is a dev dependency; the production build only includes
used classes.

### @tanstack/react-query v5
Handles data fetching, caching, and background refresh for repo list, drift reports. Removes
the need for Redux or custom state management for server state.

### react-router-dom v6
Client-side routing between RepoManager, Chat, and DriftReport pages.

### EventSource (browser built-in)
Native browser API for SSE. No library needed. The `useSSE.ts` hook wraps it with TypeScript
types and handles cleanup on component unmount.

### lucide-react
Icon library. Clean, consistent outline icons. 0.383.0 already available in Claude artifacts.

---

## Full Dependency List

### pyproject.toml
```toml
[project]
name = "repolens"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "sse-starlette>=2.1.0",
    "typer>=0.12.0",
    "rich>=13.7.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "GitPython>=3.1.43",
    "tree-sitter>=0.21.0",
    "tree-sitter-python>=0.21.0",
    "tree-sitter-go>=0.21.0",
    "tree-sitter-javascript>=0.21.0",
    "tree-sitter-typescript>=0.21.0",
    "tree-sitter-rust>=0.21.0",
    "tree-sitter-c>=0.21.0",
    "tree-sitter-cpp>=0.21.0",
    "tree-sitter-java>=0.21.0",
    "sentence-transformers>=3.0.0",
    "torch>=2.3.0",
    "lancedb>=0.10.0",
    "rank-bm25>=0.2.2",
    "networkx>=3.3",
    "httpx>=0.27.0",
    "anthropic>=0.28.0",
    "openai>=1.35.0",
    "python-multipart>=0.0.9",
    "aiofiles>=23.2.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "pre-commit>=3.7.0",
]
docs = [
    "mkdocs-material>=9.5.0",
]

[project.scripts]
repolens = "repolens.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/repolens"]

[tool.ruff]
src = ["src"]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
exclude = ["tests/"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### frontend/package.json
```json
{
  "name": "@repolens/frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint src --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "typecheck": "tsc --noEmit",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.24.0",
    "@tanstack/react-query": "^5.48.0",
    "react-markdown": "^9.0.0",
    "react-syntax-highlighter": "^15.5.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.4.0",
    "lucide-react": "^0.400.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@types/react-syntax-highlighter": "^15.5.0",
    "@typescript-eslint/eslint-plugin": "^7.15.0",
    "@typescript-eslint/parser": "^7.15.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^9.0.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.5.0",
    "vite": "^5.3.0"
  }
}
```
