""".repolensignore parsing.

:class:`IgnoreFilter` applies gitignore-style rules to decide which files the ingestion
walker is allowed to touch. Per invariant #6 in CLAUDE.md, these patterns are evaluated
*before any file is parsed*, so ``vendor/``, ``node_modules/``, generated protobufs, etc.
never reach tree-sitter.

Matching semantics (anchoring, ``**`` globs, trailing-slash directory rules, ``!`` negation)
are delegated to :mod:`pathspec`'s ``gitwildmatch`` implementation so behaviour matches
real ``.gitignore`` files.
"""

from __future__ import annotations

from pathlib import Path

import pathspec

# Patterns always excluded, even without a .repolensignore file. These mirror the shipped
# .repolensignore defaults and protect against indexing junk in bare repos. Keep in sync with
# the repo-root .repolensignore. The virtualenv/site-packages entries are essential: indexing
# a Python project with a local venv would otherwise sweep in tens of thousands of dependency
# files (per invariant #6, this must be pruned at the walker, before any file is parsed).
DEFAULT_PATTERNS: tuple[str, ...] = (
    # Version control & IDE
    ".git/",
    ".idea/",
    ".vscode/",
    # Dependencies / vendored code / virtualenvs
    "node_modules/",
    "vendor/",
    "third_party/",
    ".venv/",
    "venv/",
    "env/",
    "ENV/",
    "site-packages/",
    # Build & distribution output
    "dist/",
    "build/",
    "target/",
    "out/",
    "*.egg-info/",
    # Caches
    "__pycache__/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".pytest_cache/",
    # Generated code
    "*.generated.*",
    "*.gen.go",
    "*.pb.go",
    "*.pb.cc",
    "*.pb.h",
    "*_pb2.py",
    "*_pb2_grpc.py",
    # Minified / bundled assets
    "*.min.js",
    "*.min.css",
    "*.map",
)


class IgnoreFilter:
    """Decides whether a repo-relative path is ignored.

    Args:
        patterns: gitignore-style pattern lines.
        use_defaults: Prepend :data:`DEFAULT_PATTERNS` (later user patterns can re-include
            via ``!`` negation).
    """

    def __init__(self, patterns: list[str] | None = None, *, use_defaults: bool = True) -> None:
        lines: list[str] = list(DEFAULT_PATTERNS) if use_defaults else []
        if patterns:
            lines.extend(patterns)
        self._patterns: list[str] = [p for p in lines if _is_active(p)]
        self._spec = pathspec.PathSpec.from_lines("gitignore", self._patterns)

    @classmethod
    def from_file(cls, ignore_path: str | Path, *, use_defaults: bool = True) -> IgnoreFilter:
        """Build a filter from a ``.repolensignore`` file (missing file → defaults only)."""
        path = Path(ignore_path)
        patterns: list[str] = []
        if path.is_file():
            patterns = path.read_text(encoding="utf-8").splitlines()
        return cls(patterns, use_defaults=use_defaults)

    @classmethod
    def for_repo(cls, repo_root: str | Path, ignore_file: str = ".repolensignore") -> IgnoreFilter:
        """Load the ignore file located at ``<repo_root>/<ignore_file>``."""
        return cls.from_file(Path(repo_root) / ignore_file)

    def is_ignored(self, path: str | Path) -> bool:
        """Return ``True`` if ``path`` (relative to the repo root) should be skipped."""
        rel = self._normalise(path)
        if rel == "":
            return False
        return self._spec.match_file(rel)

    def filter(self, paths: list[str | Path]) -> list[str]:
        """Return only the paths that are **not** ignored, as POSIX strings."""
        kept: list[str] = []
        for path in paths:
            rel = self._normalise(path)
            if rel and not self._spec.match_file(rel):
                kept.append(rel)
        return kept

    @staticmethod
    def _normalise(path: str | Path) -> str:
        """Coerce to a forward-slash, repo-relative string without a leading ``./``."""
        rel = Path(path).as_posix().lstrip("/")
        if rel.startswith("./"):
            rel = rel[2:]
        return rel

    @property
    def patterns(self) -> list[str]:
        return list(self._patterns)


def _is_active(line: str) -> bool:
    """A pattern line counts if it is not blank and not a comment."""
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")
