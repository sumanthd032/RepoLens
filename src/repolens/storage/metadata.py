"""SQLite metadata store.

:class:`MetadataStore` tracks every indexed repository and its files in a single SQLite
database (``<data_dir>/metadata.db``). This is the source of truth behind the ``/api/repos``
endpoints: repo identity, indexing status, and per-file statistics. A fresh connection is
opened per operation so the store is safe to use from the server's worker threads.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from repolens.storage.paths import metadata_db_path

RepoStatus = Literal["pending", "indexing", "ready", "error"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    source      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    head_sha    TEXT,
    num_files   INTEGER NOT NULL DEFAULT 0,
    num_chunks  INTEGER NOT NULL DEFAULT 0,
    languages   TEXT NOT NULL DEFAULT '[]',
    error       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    repo_id      TEXT NOT NULL,
    path         TEXT NOT NULL,
    language     TEXT NOT NULL,
    num_chunks   INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    PRIMARY KEY (repo_id, path),
    FOREIGN KEY (repo_id) REFERENCES repos(id) ON DELETE CASCADE
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RepoRecord:
    id: str
    name: str
    source: str
    status: RepoStatus = "pending"
    head_sha: str | None = None
    num_files: int = 0
    num_chunks: int = 0
    languages: list[str] = field(default_factory=list)
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class FileRecord:
    repo_id: str
    path: str
    language: str
    num_chunks: int
    content_hash: str


class MetadataStore:
    """SQLite-backed registry of repositories and their files."""

    def __init__(self, data_dir: str | Path) -> None:
        self.db_path = metadata_db_path(data_dir)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- repos ---------------------------------------------------------------
    def upsert_repo(
        self,
        repo_id: str,
        name: str,
        source: str,
        status: RepoStatus = "pending",
        head_sha: str | None = None,
        num_files: int = 0,
        num_chunks: int = 0,
        languages: list[str] | None = None,
        error: str | None = None,
    ) -> RepoRecord:
        """Create a repo row, or update its mutable fields if it already exists."""
        now = _now()
        langs = json.dumps(languages or [])
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO repos
                    (id, name, source, status, head_sha, num_files, num_chunks,
                     languages, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    source=excluded.source,
                    status=excluded.status,
                    head_sha=excluded.head_sha,
                    num_files=excluded.num_files,
                    num_chunks=excluded.num_chunks,
                    languages=excluded.languages,
                    error=excluded.error,
                    updated_at=excluded.updated_at
                """,
                (
                    repo_id, name, source, status, head_sha, num_files, num_chunks,
                    langs, error, now, now,
                ),
            )
        record = self.get_repo(repo_id)
        assert record is not None
        return record

    def update_status(
        self, repo_id: str, status: RepoStatus, error: str | None = None
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE repos SET status=?, error=?, updated_at=? WHERE id=?",
                (status, error, _now(), repo_id),
            )

    def update_stats(
        self,
        repo_id: str,
        num_files: int,
        num_chunks: int,
        languages: list[str],
        head_sha: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE repos
                   SET num_files=?, num_chunks=?, languages=?, head_sha=?, updated_at=?
                   WHERE id=?""",
                (num_files, num_chunks, json.dumps(languages), head_sha, _now(), repo_id),
            )

    def get_repo(self, repo_id: str) -> RepoRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM repos WHERE id=?", (repo_id,)).fetchone()
        return self._to_repo(row) if row else None

    def list_repos(self) -> list[RepoRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM repos ORDER BY created_at DESC").fetchall()
        return [self._to_repo(row) for row in rows]

    def delete_repo(self, repo_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM repos WHERE id=?", (repo_id,))
        return cur.rowcount > 0

    # --- files ---------------------------------------------------------------
    def upsert_file(
        self, repo_id: str, path: str, language: str, num_chunks: int, content_hash: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO files (repo_id, path, language, num_chunks, content_hash)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(repo_id, path) DO UPDATE SET
                    language=excluded.language,
                    num_chunks=excluded.num_chunks,
                    content_hash=excluded.content_hash
                """,
                (repo_id, path, language, num_chunks, content_hash),
            )

    def list_files(self, repo_id: str) -> list[FileRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM files WHERE repo_id=? ORDER BY path", (repo_id,)
            ).fetchall()
        return [
            FileRecord(
                repo_id=row["repo_id"],
                path=row["path"],
                language=row["language"],
                num_chunks=row["num_chunks"],
                content_hash=row["content_hash"],
            )
            for row in rows
        ]

    @staticmethod
    def _to_repo(row: sqlite3.Row) -> RepoRecord:
        return RepoRecord(
            id=row["id"],
            name=row["name"],
            source=row["source"],
            status=row["status"],
            head_sha=row["head_sha"],
            num_files=row["num_files"],
            num_chunks=row["num_chunks"],
            languages=json.loads(row["languages"]),
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
