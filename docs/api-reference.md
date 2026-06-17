# API Reference

The `repolens serve` process exposes a JSON + SSE API under `/api` and serves the web UI from `/`.
Base URL in development: `http://localhost:8000`.

## Repositories

### `POST /api/repos`

Register a repository and start background indexing.

```json
{ "path": "/abs/path/to/repo", "name": "my-repo" }
```

`path` (local directory) or `url` (clone URL) is required; `name` is optional. Returns the created
repo record (`201`).

### `GET /api/repos`

List all repositories with their status and stats.

### `GET /api/repos/{id}`

Get a single repository record. `404` if unknown.

### `DELETE /api/repos/{id}`

Remove a repository and its on-disk index (`204`).

### `GET /api/repos/{id}/index`

SSE stream of indexing progress.

```
event: progress   data: {"stage": "embed", "message": "...", "current": 120, "total": 480}
event: done        data: {"stage": "done", "message": "Indexing complete"}
```

## Ask

### `POST /api/repos/{id}/ask`

```json
{ "query": "how does routing work?" }
```

Returns an SSE stream. The answer is validated before any token is emitted, so a failed answer
yields an `error` event instead of tokens.

```
event: token       data: {"text": "The router ..."}
event: citation    data: {"file": "pkg/router.go", "start": 42, "end": 67, "symbol": "handleRoute"}
event: grounding   data: {"score": 0.94, "verdict": "high"}
event: done        data: {"total_citations": 3}
event: error       data: {"message": "...", "type": "not_found" | "validation_failed"}
```

Returns `409` if the repo is not `ready`, `404` if unknown, `422` for an empty query.

## Drift

### `POST /api/repos/{id}/drift`

Run drift detection and return the full report (also cached as the latest report).

```json
{
  "repo": "my-repo",
  "counts": { "contradicted": 1, "not_found": 2, "supported": 9 },
  "has_contradictions": true,
  "findings": [
    {
      "claim": "the default timeout is 30s",
      "doc_file": "README.md", "doc_line": 42,
      "status": "contradicted", "score": 0.81,
      "code_file": "pkg/config.go", "code_start": 17, "code_end": 17,
      "code_symbol": "defaultTimeout", "code_excerpt": "const defaultTimeout = 10 * time.Second"
    }
  ]
}
```

### `GET /api/repos/{id}/drift/latest`

Return the most recent drift report. `404` if no check has been run.

### `GET /api/repos/{id}/drift/stream`

SSE stream of drift progress, ending with a `done` event carrying the full report.
