# Contributing to RepoLens

Thanks for your interest in improving RepoLens! This guide covers local setup, the commit
convention, and how to get a pull request merged.

## Development setup

RepoLens is a monorepo with a Python backend (`src/repolens/`) and a React frontend
(`frontend/`). You need [uv](https://docs.astral.sh/uv/) and Node.js 18+.

```bash
# 1. Clone and enter the repo
git clone https://github.com/sumanthd032/repolens.git
cd repolens

# 2. Install Python dependencies (creates a .venv automatically)
uv sync --extra dev

# 3. Install frontend dependencies
cd frontend && npm install && cd ..

# 4. Copy and fill in local configuration
cp .env.example .env
cp .repolens.toml.example .repolens.toml

# 5. Install git hooks
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
```

## Running the app in development

```bash
./scripts/dev.sh        # runs FastAPI (:8000) and Vite (:5173) together
```

The Vite dev server proxies `/api/*` to the FastAPI server on port 8000.

## Quality gates

Before pushing, make sure these pass — CI runs the same checks:

```bash
uv run ruff check src/         # lint
uv run ruff format --check src/  # formatting
uv run mypy src/               # type checking
uv run pytest                  # tests
cd frontend && npm run lint && npm run typecheck && npm run build
```

`pre-commit run --all-files` runs the backend checks plus prettier and commitlint.

## Commit convention

We use [Conventional Commits](https://www.conventionalcommits.org/). Each commit message is:

```
<type>(<scope>): <description>
```

Allowed types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `style`, `perf`, `ci`,
`build`, `revert`.

Examples:

```
feat(ingestion): add tree-sitter parser with semantic chunking
test(retrieval): add hybrid RRF fusion unit tests
chore(scaffold): initialise monorepo structure and dependencies
```

`commitlint` enforces this on every commit via the `commit-msg` hook.

## Pull request checklist

- [ ] Branch is up to date with `main`.
- [ ] All quality gates pass locally.
- [ ] New behaviour has tests.
- [ ] Commit messages follow the convention.
- [ ] `CHANGELOG.md` updated under `## [Unreleased]` if user-facing.

## Code of conduct

Be respectful and constructive. We want RepoLens to be a welcoming project for contributors
of all experience levels.
