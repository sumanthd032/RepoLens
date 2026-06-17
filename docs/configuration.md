# Configuration

RepoLens is configured from three sources, highest precedence first:

1. Environment variables (and a `.env` file).
2. A `.repolens.toml` file — project-local, or `~/.repolens/config.toml` globally.
3. Built-in defaults.

Copy the example files to get started:

```bash
cp .env.example .env
cp .repolens.toml.example .repolens.toml
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — | Required for the default Groq backend. |
| `ANTHROPIC_API_KEY` | — | Required when `llm_backend = "anthropic"`. |
| `OPENAI_API_KEY` | — | Required when `llm_backend = "openai"`. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Used when `llm_backend = "ollama"`. |
| `REPOLENS_DATA_DIR` | `~/.repolens` | Where all indexes are stored on disk. |
| `REPOLENS_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR`. |

## `.repolens.toml`

### `[index]`

| Key | Default | Purpose |
|---|---|---|
| `languages` | python, go, javascript, typescript, rust, c, cpp, java | Languages parsed by tree-sitter; others are skipped. |
| `embedding_model` | `jinaai/jina-embeddings-v2-base-code` | Code-aware embedding model (runs locally). |
| `max_chunk_tokens` | `512` | Soft cap before the chunker sub-splits a symbol. |
| `chunk_overlap_tokens` | `64` | Overlap between sub-chunks of a large symbol. |
| `ignore_file` | `.repolensignore` | Gitignore-style patterns applied before parsing. |

### `[retrieval]`

| Key | Default | Purpose |
|---|---|---|
| `top_k_dense` | `20` | Candidates from the dense vector index. |
| `top_k_bm25` | `20` | Candidates from the BM25 keyword index. |
| `top_k_rerank` | `8` | Candidates kept after cross-encoder reranking. |
| `graph_expansion_hops` | `1` | Caller/callee hops added around each chunk. |

### `[generation]`

| Key | Default | Purpose |
|---|---|---|
| `llm_backend` | `groq` | `groq` / `anthropic` / `openai` / `ollama`. |
| `llm_model` | `llama-3.3-70b-versatile` | Model id for the selected backend. |
| `max_answer_tokens` | `2048` | Maximum tokens per generated answer. |
| `max_retries` | `2` | Regenerations allowed when citation validation fails. |
| `grounding_threshold` | `0.5` | Minimum grounding score to accept an answer. |

### `[drift]`

| Key | Default | Purpose |
|---|---|---|
| `ci_mode` | `false` | `repolens drift --ci` exits non-zero on contradictions. |
| `severity_threshold` | `low` | Minimum severity reported: `low` / `medium` / `high`. |

## Ignoring files

`.repolensignore` uses gitignore syntax and is applied **before** any file is read. Sensible
defaults (`vendor/`, `node_modules/`, generated protobuf, `dist/`, …) ship out of the box.
