# CLAUDE.md — RepoLens

> A local-first RAG engine that lets OSS contributors ask questions about any repository and get
> answers grounded exclusively in the actual checked-out code — with file/line citations, zero
> reliance on model prior knowledge, and automatic detection of where docs have drifted from code.

---

## ⚠️ CRITICAL INSTRUCTIONS — READ BEFORE DOING ANYTHING

### 1. Git commits
- After completing any major unit of work (a module, a feature, a set of tests), stage and commit immediately.
- Use **conventional commits**: `git add -A && git commit -m "<type>(<scope>): <description>"`
- Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `style`, `perf`
- Examples:
  - `feat(ingestion): add tree-sitter parser with semantic chunking`
  - `test(retrieval): add hybrid RRF fusion unit tests`
  - `chore(scaffold): initialise monorepo structure and dependencies`
- **NEVER add Claude as a co-author.** Do not include `Co-authored-by:`, `Co-authored by:`, or any
  AI attribution anywhere in commit messages, PR descriptions, or code comments.

### 2. Step-by-step execution
- The project is divided into **10 steps** (see `docs/STEPS.md`).
- When the user says **"do step N"** or **"start step N"**, implement **only that step** — nothing
  from future steps, no "getting a head start".
- Do not proceed to the next step until the user explicitly asks.
- Update the **Current Implementation Status** section at the bottom of this file when starting
  and completing each step.

### 3. Post-step explanation (mandatory)
After completing every step, write a structured explanation in this format:

```
## Step N — Completion Report

### What was built
[List every file created or modified with a one-line description of each]

### Why each component was built this way
[For each non-trivial design decision, explain the reasoning]

### How this contributes to the final goal
[Explain how this step's output is used by downstream steps and by the finished product]

### Why this step matters
[What would break or be impossible without this step]

### What the next step builds on top of this
[Bridge to step N+1]
```

### 4. UI requirements
- The UI must be the **"Observatory" design** described in `docs/UI_SPEC.md`.
- No generic shadcn clones, no plain white backgrounds, no Bootstrap aesthetics.
- Every component must be production-quality — no placeholders or TODO stubs in the UI.
- The design uses a deep space colour palette, glass morphism surfaces, and a signature
  purple-to-blue gradient. All details are in `docs/UI_SPEC.md`.

---

## Project Overview

### The problem
New contributors face a cold-start wall on large OSS projects. Docs are incomplete or stale. LLM
assistants hallucinate confidently because they "remember" an older version of the project from
training data. There is no tool that answers "how does X actually work **in this repo, at this
commit**" with verifiable evidence.

### The solution — three pillars

**Pillar 1 — Grounding enforcement**
Every answer sentence must cite a `file:line-range` span. The pipeline post-validates every
citation by re-opening the file and checking the range exists and is relevant. If retrieval returns
nothing relevant, the system says "not found in this codebase" rather than letting the LLM fill
from memory. A **grounding score** (NLI entailment) is computed per answer and shown in the UI.

**Pillar 2 — Code-native retrieval**
Source files are parsed with tree-sitter into semantic units (functions, classes, structs). Each
chunk carries metadata: file path, symbol name, signature, docstring. A **symbol graph** tracks
caller/callee relationships so graph expansion can retrieve callers and callees alongside the
primary match. Retrieval is **hybrid**: dense embeddings + BM25 exact-match, fused with RRF, then
re-ranked with a cross-encoder.

**Pillar 3 — Doc-drift detection**
A separate mode indexes documentation (README, `/docs`, docstrings, code comments) and code
separately. For each factual claim in the docs ("the default timeout is 30s", "returns nil on
error"), it retrieves the corresponding code and runs NLI entailment: **supported / contradicted /
not found**. The output is a markdown report of suspected stale documentation with doc location
+ code location side by side. This report is CI-compatible (`--ci` flag exits non-zero on new
findings).

---

## Architecture

See `docs/ARCHITECTURE.md` for the full breakdown. Summary:

```
Browser (React)
    │  HTTP requests ↓   ↑ SSE response stream
FastAPI server
    │
    ├─── Ingestion pipeline (index time)
    │    git walker → tree-sitter → chunker → symbol graph → embedder + BM25 → Storage
    │
    ├─── Retrieval engine (query time)
    │    Storage → hybrid (dense + BM25) → RRF → reranker → graph expander
    │
    ├─── Generation + Verification
    │    retrieved chunks → grounded prompt → LLM → citation validator → grounding scorer
    │
    └─── Drift detector (drift mode)
         Storage → claim extractor → NLI entailment → markdown report
```

---

## Tech Stack Summary

See `docs/TECHSTACK.md` for full rationale and version pinning.

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| CLI | typer + rich |
| Server | FastAPI + uvicorn[standard] |
| SSE streaming | sse-starlette |
| Config | pydantic-settings + `.repolens.toml` |
| Git ops | GitPython |
| Code parsing | tree-sitter (py bindings) + grammar packages |
| Embeddings | `jinaai/jina-embeddings-v2-base-code` via sentence-transformers |
| Vector store | LanceDB (embedded, no server) |
| Keyword search | rank_bm25 |
| Symbol graph | NetworkX |
| Metadata store | SQLite (stdlib) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Grounding scorer | `cross-encoder/nli-deberta-v3-small` |
| LLM (default) | Anthropic Claude via `anthropic` SDK |
| LLM (alt) | OpenAI via `openai` SDK |
| LLM (local) | Ollama via `httpx` |
| Frontend | React 18 + TypeScript + Vite |
| Styling | Tailwind CSS v3 |
| Data fetching | @tanstack/react-query |
| Routing | react-router-dom v6 |
| Package mgmt (py) | uv |
| Linting/format (py) | ruff + mypy |
| Linting/format (ts) | eslint + prettier |
| Pre-commit | pre-commit hooks |
| Build backend | hatchling |

---

## Repo Structure

```
repolens/
├── .github/workflows/          # CI, release, self-index
├── src/repolens/               # Python package (src layout)
│   ├── api/                    # FastAPI route handlers
│   ├── ingestion/              # Index-time pipeline
│   ├── storage/                # LanceDB + SQLite + graph
│   ├── retrieval/              # Hybrid search + reranker + expander
│   ├── generation/             # Prompt + LLM backends + validator + scorer
│   │   └── llm/                # BaseLLMClient, Anthropic, OpenAI, Ollama
│   ├── drift/                  # Claim extractor + NLI checker + reporter
│   └── utils/                  # Cache + ignore parser + logger
├── frontend/                   # React + Vite + TypeScript
│   └── src/
│       ├── pages/              # RepoManager, Chat, DriftReport
│       ├── components/         # ChatMessage, CitationCard, GroundingBadge, etc.
│       ├── hooks/              # useSSE, useRepos
│       └── lib/                # api.ts, types.ts
├── tests/
│   ├── unit/                   # Fast, no external deps
│   ├── integration/            # Needs local models
│   └── e2e/                    # Full server
├── docs/                       # Architecture, techstack, steps, UI spec
├── scripts/                    # dev.sh, build.sh, eval.sh
└── [root config files]
```

Full tree with annotations: `docs/REPO_STRUCTURE.md` (generated from the interactive widget in
the design conversation).

---

## Key Invariants — Never Violate

1. **Every answer sentence must cite a `file:line-range` span.** No uncited claims.
2. **The citation validator must re-open the file and verify the cited range.** A citation that
   points to a non-existent line range must cause the answer to be rejected and regenerated
   (max 2 retries), not silently passed through.
3. **If retrieval returns no relevant chunks, return a structured "not found" response.** Never
   allow the LLM to fill the answer from its parametric memory.
4. **The grounding score must be computed for every answer before it is returned.** It is not
   optional metadata; it is part of the answer contract.
5. **All data is local.** Vectors, BM25 index, symbol graph, metadata — everything is stored on
   disk in `~/.repolens/`. The only network calls are LLM API calls (and only when using the
   Anthropic/OpenAI backends; Ollama is fully local).
6. **`.repolensignore` patterns are applied before any file is parsed.** `vendor/`, `node_modules/`,
   generated protobuf files, etc. must be excluded at the walker level.
7. **The `repolens serve` command starts the FastAPI server which also serves the React frontend
   build as static files from `src/repolens/static/`.** The `scripts/build.sh` script copies
   `frontend/dist/` to that location. Single process, single port (`localhost:8000`).

---

## Environment Variables

Declared in `.env.example`. Copy to `.env` before running.

```bash
ANTHROPIC_API_KEY=sk-ant-...        # Required for default LLM backend
OPENAI_API_KEY=sk-...               # Optional: for OpenAI backend
OLLAMA_BASE_URL=http://localhost:11434  # Optional: for local Ollama backend
REPOLENS_DATA_DIR=~/.repolens       # Where all indexes are stored
REPOLENS_LOG_LEVEL=INFO
```

---

## Configuration File

`.repolens.toml` at the project root (or `~/.repolens/config.toml` for global config).
Copy from `.repolens.toml.example`.

```toml
[index]
languages = ["python", "go", "javascript", "typescript", "rust", "c", "cpp", "java"]
embedding_model = "jinaai/jina-embeddings-v2-base-code"
max_chunk_tokens = 512
chunk_overlap_tokens = 64
ignore_file = ".repolensignore"

[retrieval]
top_k_dense = 20
top_k_bm25 = 20
top_k_rerank = 8
graph_expansion_hops = 1

[generation]
llm_backend = "anthropic"          # anthropic | openai | ollama
llm_model = "claude-sonnet-4-5"
max_answer_tokens = 2048
max_retries = 2
grounding_threshold = 0.5         # Minimum grounding score to accept answer

[drift]
ci_mode = false                    # Exit non-zero if new findings found
severity_threshold = "low"         # low | medium | high
```

---

## API Endpoints (FastAPI)

```
GET  /                              → serves React SPA (index.html)
POST /api/repos                     → add a repo (body: {url, name})
GET  /api/repos                     → list all repos with status
GET  /api/repos/{id}                → get single repo details
DELETE /api/repos/{id}             → remove repo and its index
GET  /api/repos/{id}/index         → SSE stream: indexing progress events
POST /api/repos/{id}/ask           → SSE stream: answer tokens + final citations
POST /api/repos/{id}/drift         → trigger drift detection (background)
GET  /api/repos/{id}/drift/latest  → get latest drift report (JSON)
GET  /api/repos/{id}/drift/stream  → SSE stream: drift progress events
```

SSE events from `/ask`:
```
event: token        data: {"text": "The router handles..."}
event: citation     data: {"file": "pkg/router.go", "start": 42, "end": 67, "symbol": "handleRoute"}
event: grounding    data: {"score": 0.94, "verdict": "high"}
event: done         data: {"total_citations": 3}
event: error        data: {"message": "...", "type": "not_found"|"validation_failed"}
```

---

## Current Implementation Status

```
COMPLETED_STEPS: [1]
CURRENT_STEP: 1 (complete)
NEXT_STEP: 2
```

Update this section at the start and end of each step.
