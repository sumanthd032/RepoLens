#!/usr/bin/env bash
# Retrieval & grounding evaluation harness.
# Indexes a target repository (default: RepoLens itself) and reports MRR@5, Recall@5, and the
# average grounding score over tests/eval/cases.py.
#
# Usage: ./scripts/eval.sh [REPO_PATH]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TARGET="${1:-$ROOT}"
echo "Running RepoLens evaluation against: $TARGET"
uv run python -m tests.eval.run_eval "$TARGET"
