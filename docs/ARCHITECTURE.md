# Architecture — RepoLens

## System Overview

RepoLens has three distinct operational modes sharing the same storage layer:

| Mode | Trigger | Flow |
|---|---|---|
| **Index** | `repolens index <path>` or UI "Add Repo" | walk → parse → embed → store |
| **Ask** | `repolens ask "..."` or UI chat | retrieve → generate → verify → stream |
| **Drift** | `repolens drift` or UI "Run Drift Check" | compare docs vs code → entailment → report |

---

## Layer 1 — Web Interface

### Browser (React frontend)
Three pages served as a single-page application:
- **Repo Manager** — add a repo by GitHub URL or local path, view all indexed repos, monitor
  indexing progress via SSE stream.
- **Chat** — select a repo, ask questions, see streaming answers with inline citations and a
  grounding score ring.
- **Drift Report** — view the latest drift report for a repo, filter by severity
  (supported / contradicted / not found).

### FastAPI server (`src/repolens/server.py`)
- Mounts all API routers under `/api/`
- Serves the React build (`frontend/dist/`) as static files at `/`
- Handles CORS for local dev (`localhost:5173` ↔ `localhost:8000`)
- Background tasks for indexing and drift detection (FastAPI `BackgroundTasks`)

### Streaming (SSE)
All long-running operations use Server-Sent Events (SSE) via `sse-starlette`:
- Index progress: `event: progress data: {"file": "...", "done": 23, "total": 847}`
- Ask stream: token events → citation event → grounding event → done
- Drift progress: `event: claim data: {"claim": "...", "status": "checking", "total": 45}`

---

## Layer 2 — Ingestion Pipeline

All ingestion is managed through `src/repolens/ingestion/`. The pipeline is run in a background
task; progress is streamed to the frontend via SSE.

### walker.py — Git walker
- Uses `GitPython` to walk all files in the repository
- Reads the indexed commit SHA from SQLite metadata
- On re-index: computes `git diff --name-only <old_sha> HEAD` to find changed files only
  (incremental indexing)
- Applies `.repolensignore` patterns via `utils/ignore.py` before yielding any path
- Yields `(file_path, language, content)` tuples

### parser.py — Tree-sitter AST parser
- Loads the appropriate tree-sitter grammar for each language (auto-detected by extension)
- Supported: Python, Go, JavaScript, TypeScript, Rust, C, C++, Java
- Parses the file into an AST and walks it to extract semantic units:
  - Functions / methods (with signature, docstring, body)
  - Classes / structs / interfaces (header only for the outer chunk; methods are separate chunks)
  - Top-level variable declarations with doc comments
- Returns `List[ParsedChunk]` where each chunk has: `file_path`, `symbol_name`, `symbol_type`,
  `signature`, `docstring`, `body`, `start_line`, `end_line`, `language`

### chunker.py — Semantic chunker
- Receives `ParsedChunk` objects from the parser
- If a chunk's token count exceeds `max_chunk_tokens` (default 512), slides within it with
  `chunk_overlap_tokens` overlap — never cuts at a line that is inside a nested block
- Chunks below a minimum size (default 10 tokens) are discarded (empty functions, stubs)
- Returns `List[IndexChunk]` — final chunks ready for embedding

### graph.py — Symbol graph builder
- Walks all parsed chunks and extracts:
  - Function calls (callers → callees)
  - Import relationships (importer → imported module/symbol)
  - Interface implementations
- Builds a directed `networkx.DiGraph` with nodes = symbol IDs, edges labelled by relationship type
- The graph is built once per file during indexing and merged into the global graph in storage

### embedder.py — Dense embedder
- Loads `jinaai/jina-embeddings-v2-base-code` via `sentence-transformers`
- Embeds each chunk's `signature + docstring + body` (truncated at 8192 tokens)
- Maintains a disk cache keyed by `sha256(content + model_name)` — unchanged chunks are never
  re-embedded
- Returns `np.ndarray` of shape `(n_chunks, 768)`

### bm25.py — BM25 index builder
- Tokenises each chunk (simple whitespace + CamelCase split for identifiers)
- Builds a `rank_bm25.BM25Okapi` index
- Serialises to disk with `pickle` alongside the chunk IDs for retrieval mapping

---

## Layer 3 — Storage

All data is stored in `~/.repolens/<repo_id>/` by default.

### vector.py — LanceDB
- One LanceDB table per repo: `chunks`
- Schema: `chunk_id`, `file_path`, `symbol_name`, `symbol_type`, `language`, `start_line`,
  `end_line`, `embedding` (float32 vector), `body_preview` (first 200 chars)
- Supports ANN search with `metric="cosine"` and a `top_k` filter
- Also used as the source for BM25 (chunks are retrieved by ID from LanceDB after BM25 ranks them)

### metadata.py — SQLite
Tables:
```sql
repos (id, name, url, local_path, indexed_commit_sha, indexed_at, status, chunk_count)
files (id, repo_id, path, language, last_modified, chunk_count)
```
- Used to track indexing state, enable incremental re-indexing, and power the repo list in the UI

### graph.py — NetworkX + SQLite
- The symbol graph (`networkx.DiGraph`) is serialised to SQLite as an adjacency list:
  ```sql
  graph_edges (repo_id, source_symbol, target_symbol, relationship, file_path)
  ```
- Loaded into memory as a NetworkX graph on server startup (or lazy-loaded per repo)

---

## Layer 4 — Retrieval Engine

### hybrid.py — RRF fusion
- Runs **dense retrieval** (LanceDB ANN, top-K=20) and **BM25 retrieval** (top-K=20) in parallel
- Fuses results with **Reciprocal Rank Fusion**:
  ```
  RRF_score(d) = Σ 1 / (k + rank_i(d))   where k=60
  ```
- Returns top-K=20 fused candidates ordered by RRF score
- Before dense retrieval, applies **HyDE** (Hypothetical Document Embedding): asks the LLM to
  generate a short hypothetical code snippet that would answer the query, then embeds that
  instead of the raw query string. This dramatically improves recall for natural-language queries
  against code.

### reranker.py — Cross-encoder
- Loads `cross-encoder/ms-marco-MiniLM-L-6-v2` via `sentence-transformers`
- Scores each (query, chunk) pair with the cross-encoder
- Returns top-K=8 re-ranked candidates

### expander.py — Graph expansion
- For each of the top-K=8 reranked chunks, looks up the symbol in the NetworkX graph
- Retrieves immediate callers and callees (1-hop neighbours, bounded to avoid explosion)
- Fetches those additional chunks from LanceDB
- Deduplicates and returns the expanded context window (≤ 12 chunks total)

---

## Layer 5 — Generation + Verification

### prompt.py — Grounded system prompt
The system prompt instructs the LLM:
- To answer **only** from the provided code chunks
- To format every factual claim as `[file:start-end]` citation inline
- To emit a JSON block at the end: `{"citations": [...], "not_found": bool}`
- To say "I cannot find this in the codebase" if the context does not contain the answer
- The prompt includes the retrieved chunks, each labelled with file path, symbol name, and lines

### llm/base.py — BaseLLMClient
Abstract base class with a single required method:
```python
async def stream(self, messages: list[dict], system: str) -> AsyncIterator[str]
```
Implementations: `AnthropicClient`, `OpenAIClient`, `OllamaClient`

### validator.py — Citation validator
After the LLM produces an answer:
1. Parse all `[file:start-end]` citations from the text
2. For each citation: open the file on disk, check the line range exists
3. For each citation: fetch the chunk from LanceDB and compute cosine similarity between the
   cited text and the answer sentence that references it
4. If any citation is invalid (file not found, line range out of bounds, similarity < 0.3):
   reject the answer and trigger regeneration (max 2 retries)
5. If all retries fail: return a structured error with `type: "validation_failed"`

### scorer.py — NLI grounding scorer
- Loads `cross-encoder/nli-deberta-v3-small`
- For each sentence in the answer, runs NLI against its cited chunk
- Returns `{"score": float, "verdict": "high"|"medium"|"low"|"none"}`
  - high: ≥ 0.8   medium: ≥ 0.6   low: ≥ 0.4   none: < 0.4
- The score is streamed to the frontend as the final SSE event before `done`

---

## Drift Detection Mode

### extractor.py — Claim extractor
- Indexes the repo's documentation separately: README.md, `/docs/**/*.md`, all docstrings and
  inline code comments
- Uses the LLM to extract factual claims from doc text in structured form:
  ```json
  {"claim": "the default timeout is 30s", "doc_file": "README.md", "doc_line": 42}
  ```

### checker.py — NLI entailment checker
For each extracted claim:
1. Run retrieval against the code index using the claim as the query
2. If no relevant code found: `status = "not_found"`
3. Run NLI (`cross-encoder/nli-deberta-v3-small`) between the claim and the top retrieved chunk
4. Map NLI output to: `entails → "supported"`, `neutral → "not_found"`, `contradicts → "contradicted"`

### reporter.py — Report generator
- Collects all claims with their status
- Generates a structured markdown report:
  ```markdown
  ## Contradicted claims (3)
  | Doc location | Claim | Code location | Code says |
  |---|---|---|---|
  | README.md:42 | default timeout is 30s | pkg/config.go:17 | timeout = 10 * time.Second |
  ```
- `--ci` flag: if any `contradicted` findings exist, exit code 1 (for CI pipelines)

---

## Data Flow Diagrams

### Index time
```
repolens index ./myrepo
    │
    ▼
walker.py ──(files)──► parser.py ──(ParsedChunk)──► chunker.py ──(IndexChunk)──►
    │                                                                              │
    │                                                                              ▼
    │                                                                       embedder.py ──► LanceDB
    │                                                                              │
    │                                                                       bm25.py ──────► BM25 index
    │                                                                              │
    └──────────────────────────────────────────────────► graph.py ──► SQLite graph
                                                                                   │
                                                                             metadata.py ──► SQLite repos/files
```

### Query time
```
User question
    │
    ▼
HyDE expansion (hypothetical code snippet)
    │
    ▼
hybrid.py ──(dense query + BM25 query, parallel)──► RRF fusion ──► top-20 candidates
    │
    ▼
reranker.py ──► top-8 candidates
    │
    ▼
expander.py ──(graph lookup)──► expanded context (≤12 chunks)
    │
    ▼
prompt.py ──(grounded system prompt + chunks)──► LLM
    │
    ▼
validator.py ──(re-open files, check citations)──► accept | reject | not_found
    │
    ▼
scorer.py ──(NLI per sentence)──► grounding score
    │
    ▼
SSE stream ──► browser
```

---

## Key Design Decisions

### Why src layout for the Python package?
The `src/` layout prevents the package from being accidentally importable from the project root
during testing. `pip install -e .` (or `uv sync`) installs the package properly, ensuring tests
run against the installed version, not the raw source tree.

### Why LanceDB over ChromaDB or Qdrant?
LanceDB is embedded (no server process), columnar (efficient for batch operations), and supports
hybrid search natively. ChromaDB is simpler but slower at scale. Qdrant requires a server.
For a local-first tool where a developer runs it on their laptop, embedded is the right choice.

### Why SSE over WebSockets?
SSE is unidirectional (server → client), which matches the answer streaming pattern perfectly.
It's simpler than WebSockets (no handshake, no keep-alive management), works through proxies and
firewalls without special configuration, and is natively supported by browsers via `EventSource`.

### Why HyDE for dense retrieval?
Natural language queries ("how does authentication work") produce embeddings in a different
semantic space than code embeddings. HyDE bridges this gap by generating a hypothetical code
snippet that would answer the query, then embedding that instead. The hypothetical snippet's
embedding is much closer to actual code in embedding space, dramatically improving recall.

### Why NLI for grounding scoring?
NLI (Natural Language Inference) models are trained to determine whether a "hypothesis" is
entailed by, contradicts, or is neutral to a "premise". By treating the answer sentence as the
hypothesis and the cited code chunk as the premise, we get a well-calibrated grounding signal
without any task-specific fine-tuning.
