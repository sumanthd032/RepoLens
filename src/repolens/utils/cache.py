"""Content-addressed disk cache.

:class:`DiskCache` persists arbitrary Python values keyed by the SHA-256 of their source
content. The ingestion embedder (Step 4) uses this to avoid re-embedding chunks whose body
has not changed: it hashes a chunk's content, checks the cache, and only runs the model on a
miss. ``hits`` / ``misses`` counters expose cache effectiveness for tests and metrics.

Values are stored with :mod:`pickle`, so the cache is process-local and trusted-input only
(it caches our own embeddings and intermediate artefacts, never untrusted data).
"""

from __future__ import annotations

import hashlib
import pickle
from pathlib import Path
from typing import Any

_VALUE_SUFFIX = ".pkl"


class DiskCache:
    """A simple, thread-unsafe, content-addressed cache backed by files on disk.

    Args:
        cache_dir: Directory to hold cache entries. Created if it does not exist.
        namespace: Optional sub-directory to isolate unrelated caches (e.g. ``"embeddings"``).
    """

    def __init__(self, cache_dir: str | Path, namespace: str | None = None) -> None:
        base = Path(cache_dir).expanduser()
        self._dir = base / namespace if namespace else base
        self._dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(content: str | bytes) -> str:
        """Return the SHA-256 hex digest of ``content`` to use as a cache key."""
        data = content.encode("utf-8") if isinstance(content, str) else content
        return hashlib.sha256(data).hexdigest()

    def _path_for(self, key: str) -> Path:
        return self._dir / f"{key}{_VALUE_SUFFIX}"

    def has(self, key: str) -> bool:
        """Return ``True`` if an entry exists for ``key`` (does not count as a hit/miss)."""
        return self._path_for(key).is_file()

    def get(self, key: str, default: Any = None) -> Any:
        """Return the cached value for ``key``, or ``default`` on a miss.

        Increments :attr:`hits` on a hit and :attr:`misses` on a miss. A corrupt or
        unreadable entry is treated as a miss and removed.
        """
        path = self._path_for(key)
        if not path.is_file():
            self.misses += 1
            return default
        try:
            with path.open("rb") as fh:
                value = pickle.load(fh)
        except (pickle.UnpicklingError, EOFError, OSError):
            self.invalidate(key)
            self.misses += 1
            return default
        self.hits += 1
        return value

    def set(self, key: str, value: Any) -> None:
        """Store ``value`` under ``key``, written atomically via a temp file + rename."""
        path = self._path_for(key)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as fh:
            pickle.dump(value, fh, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(path)

    def get_or_set(self, key: str, factory: Any) -> Any:
        """Return the cached value for ``key``, computing and storing it via ``factory`` on a miss."""
        sentinel = object()
        value = self.get(key, sentinel)
        if value is sentinel:
            value = factory()
            self.set(key, value)
        return value

    def invalidate(self, key: str) -> bool:
        """Delete the entry for ``key``. Returns ``True`` if something was removed."""
        path = self._path_for(key)
        if path.is_file():
            path.unlink()
            return True
        return False

    def clear(self) -> None:
        """Remove every entry and reset the hit/miss counters."""
        for entry in self._dir.glob(f"*{_VALUE_SUFFIX}"):
            entry.unlink()
        self.hits = 0
        self.misses = 0

    def reset_stats(self) -> None:
        """Reset the hit/miss counters without touching cached data."""
        self.hits = 0
        self.misses = 0

    @property
    def directory(self) -> Path:
        return self._dir
