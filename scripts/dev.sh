#!/usr/bin/env bash
# Run the FastAPI backend (:8000) and the Vite frontend dev server (:5173) together.
# The Vite config proxies /api/* to the backend. Ctrl-C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

cleanup() {
  echo
  echo "Shutting down dev servers..."
  kill 0
}
trap cleanup EXIT INT TERM

echo "Starting FastAPI backend on http://localhost:8000 ..."
uv run uvicorn repolens.server:create_app --factory --reload --host 0.0.0.0 --port 8000 &

echo "Starting Vite frontend on http://localhost:5173 ..."
(cd frontend && npm run dev) &

wait
