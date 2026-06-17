"""Repository file walker.

:class:`GitWalker` traverses a checked-out repository and yields the source files that are
eligible for indexing — applying the :class:`~repolens.utils.ignore.IgnoreFilter` *before*
any file is read (Invariant #6) and detecting language by file extension. Files in
unsupported languages are skipped silently (their extension maps to ``None``).

``get_changed_files`` supports incremental re-indexing by diffing the working tree against a
previously indexed commit.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from git import InvalidGitRepositoryError, Repo

from repolens.utils.ignore import IgnoreFilter
from repolens.utils.logger import get_logger

logger = get_logger("ingestion.walker")

# File extension → tree-sitter language name. Extensions not listed are skipped.
EXTENSION_LANGUAGES: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".go": "go",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    ".java": "java",
}

# Files larger than this are assumed to be generated/data blobs and skipped.
MAX_FILE_BYTES = 1_000_000


@dataclass(frozen=True)
class WalkedFile:
    """A single eligible file produced by the walker."""

    path: str  # repo-relative, POSIX
    language: str
    content: str


def detect_language(path: str | Path) -> str | None:
    """Return the tree-sitter language for ``path`` by extension, or ``None`` if unsupported."""
    return EXTENSION_LANGUAGES.get(Path(path).suffix.lower())


class GitWalker:
    """Yields eligible source files from a repository.

    Args:
        repo_path: Path to the repository root.
        ignore_filter: Filter applied to repo-relative paths before reading. If ``None``,
            the repo's ``.repolensignore`` (plus built-in defaults) is loaded.
        languages: Optional whitelist of language names to include. ``None`` means all
            supported languages.
    """

    def __init__(
        self,
        repo_path: str | Path,
        ignore_filter: IgnoreFilter | None = None,
        languages: set[str] | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).expanduser().resolve()
        if not self.repo_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {self.repo_path}")
        self.ignore = ignore_filter or IgnoreFilter.for_repo(self.repo_path)
        self.languages = languages

    def walk(self) -> Iterator[WalkedFile]:
        """Yield every eligible :class:`WalkedFile` under the repository root."""
        for abs_path in self._iter_candidate_paths():
            rel = abs_path.relative_to(self.repo_path).as_posix()
            if self.ignore.is_ignored(rel):
                continue
            language = detect_language(abs_path)
            if language is None or (self.languages and language not in self.languages):
                continue
            content = self._read(abs_path)
            if content is None:
                continue
            yield WalkedFile(path=rel, language=language, content=content)

    def _iter_candidate_paths(self) -> Iterator[Path]:
        """Yield files on disk, pruning ignored directories early for efficiency."""
        stack: list[Path] = [self.repo_path]
        while stack:
            current = stack.pop()
            try:
                entries = sorted(current.iterdir())
            except OSError as exc:  # pragma: no cover - permission/race edge case
                logger.warning("Cannot list %s: %s", current, exc)
                continue
            for entry in entries:
                rel = entry.relative_to(self.repo_path).as_posix()
                if entry.is_symlink():
                    continue
                if entry.is_dir():
                    # Match directories with a trailing slash so dir-only rules apply.
                    if not self.ignore.is_ignored(rel + "/"):
                        stack.append(entry)
                elif entry.is_file():
                    yield entry

    def _read(self, abs_path: Path) -> str | None:
        """Read a UTF-8 text file, skipping oversized or binary files."""
        try:
            if abs_path.stat().st_size > MAX_FILE_BYTES:
                logger.debug("Skipping oversized file: %s", abs_path)
                return None
            data = abs_path.read_bytes()
        except OSError as exc:  # pragma: no cover - race/permission edge case
            logger.warning("Cannot read %s: %s", abs_path, exc)
            return None
        if b"\x00" in data:
            logger.debug("Skipping binary file: %s", abs_path)
            return None
        return data.decode("utf-8", errors="replace")


def get_changed_files(repo_path: str | Path, since_sha: str) -> list[str]:
    """Return repo-relative paths changed since ``since_sha`` (for incremental indexing).

    Includes both committed changes (``since_sha..HEAD``) and uncommitted working-tree
    changes. Deleted files are excluded since they no longer need parsing.
    """
    root = Path(repo_path).expanduser().resolve()
    try:
        repo = Repo(root)
    except InvalidGitRepositoryError as exc:
        raise InvalidGitRepositoryError(f"Not a git repository: {root}") from exc

    changed: set[str] = set()
    # Committed changes between the given commit and the current HEAD.
    for diff in repo.commit(since_sha).diff(repo.head.commit):
        if diff.change_type != "D" and diff.b_path:
            changed.add(diff.b_path)
    # Uncommitted (staged + unstaged) changes in the working tree.
    for diff in repo.index.diff(None) + repo.index.diff(repo.head.commit):
        if diff.change_type != "D" and diff.b_path:
            changed.add(diff.b_path)
    # Untracked files.
    changed.update(repo.untracked_files)

    return sorted(p for p in changed if detect_language(p) is not None)
