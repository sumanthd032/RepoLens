# Contributing

Development setup, quality gates, and the commit convention live in the repository's
[CONTRIBUTING.md](https://github.com/sumanthd032/repolens/blob/main/CONTRIBUTING.md).

In short:

```bash
uv sync --extra dev                 # Python deps (creates .venv)
cd frontend && npm install && cd .. # frontend deps
./scripts/dev.sh                    # run API (:8000) + Vite (:5173)
```

Before pushing, run the same checks CI runs:

```bash
uv run ruff check src/
uv run mypy src/
uv run pytest
cd frontend && npm run lint && npm run typecheck && npm run build
```

Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat`, `fix`, `test`, `docs`, `refactor`, `chore`, …).
