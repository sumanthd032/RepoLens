# Quickstart

Get RepoLens indexing a repository and answering grounded questions in a few minutes.

## 1. Install

RepoLens needs Python 3.11+.

```bash
pip install repolens
```

Or run it fully containerised (no Python setup needed):

```bash
GROQ_API_KEY=gsk_... docker compose up
# open http://localhost:8000
```

## 2. Configure an LLM backend

RepoLens uses **Groq** by default — a free, OpenAI-compatible hosted tier. Get a key at
[console.groq.com/keys](https://console.groq.com/keys) and export it:

```bash
export GROQ_API_KEY=gsk_...
```

To use another backend, set `llm_backend` in `.repolens.toml` to `anthropic`, `openai`, or
`ollama` (fully local) and provide the matching key. See [Configuration](configuration.md).

!!! note "Local models stay local"
    Embeddings, reranking, and the NLI grounding model all run on your machine. The only network
    calls are to the chosen LLM backend (and none at all with Ollama).

## 3. Index a repository

```bash
repolens index ./path/to/repo
```

This walks the repo, parses it with tree-sitter, embeds the chunks, and builds the BM25 index and
symbol graph under `~/.repolens/`. The command prints the repo **id** you'll use to query it.

## 4. Ask a question

```bash
repolens ask "how does request routing work?" --repo <id>
```

Every sentence in the answer cites a `file:line-range` span, each citation is re-checked against
the file on disk, and a grounding score is printed. If the code can't answer, RepoLens says so
rather than guessing.

## 5. Check for documentation drift

```bash
repolens drift --repo <id>          # print a markdown report
repolens drift --repo <id> --ci     # exit non-zero if docs contradict code
```

## 6. Launch the web UI

```bash
repolens serve
# open http://localhost:8000
```

The Observatory UI gives you repository management, streaming chat with expandable citation cards
and a grounding ring, and the drift report — all from one process on one port.

## Next steps

- [Configuration reference](configuration.md)
- [API reference](api-reference.md)
- [Architecture](ARCHITECTURE.md)
