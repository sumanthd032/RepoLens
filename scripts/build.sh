#!/usr/bin/env bash
# Build the React frontend and copy the output into the Python package so that
# `repolens serve` can serve it as static files from src/repolens/static/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"

npm run build
rm -rf ../src/repolens/static
cp -r dist ../src/repolens/static
echo "✓ Frontend built and copied to src/repolens/static/"
