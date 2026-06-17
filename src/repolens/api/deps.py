"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, status

if TYPE_CHECKING:
    from repolens.api.engine import AppState
    from repolens.storage.metadata import RepoRecord


def get_state(request: Request) -> AppState:
    """Return the process-wide :class:`AppState` attached to the app."""
    return request.app.state.engine  # type: ignore[no-any-return]


def get_repo(repo_id: str, state: AppState = Depends(get_state)) -> RepoRecord:
    """Resolve a repo id to its record, raising 404 if it does not exist."""
    repo = state.metadata.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Repo {repo_id!r} not found")
    return repo
