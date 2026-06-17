"""Repository management endpoints: add, list, get, delete, and indexing progress (SSE)."""

from __future__ import annotations

import asyncio
import shutil
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from sse_starlette.sse import EventSourceResponse

from repolens.api.deps import get_repo, get_state
from repolens.api.engine import AppState, sse
from repolens.storage.paths import repo_dir
from repolens.storage.pipeline import IndexProgress
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from repolens.storage.metadata import RepoRecord

logger = get_logger("api.repos")

router = APIRouter(prefix="/api/repos", tags=["repos"])

_TERMINAL = {"done", "error"}


class AddRepoRequest(BaseModel):
    """Request body for adding a repository (a local path or a clone URL)."""

    name: str | None = None
    path: str | None = None
    url: str | None = None

    @model_validator(mode="after")
    def _require_source(self) -> AddRepoRequest:
        if not self.path and not self.url:
            raise ValueError("either 'path' or 'url' is required")
        return self


def _clone_dir(state: AppState, repo_id: str) -> Path:
    return Path(state.data_dir) / "clones" / repo_id


async def _resolve_source(state: AppState, req: AddRepoRequest, repo_id: str) -> tuple[str, str]:
    """Return ``(source_path, name)`` for the request, cloning a URL if needed."""
    if req.path:
        root = Path(req.path).expanduser().resolve()
        if not root.is_dir():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Not a directory: {root}")
        return str(root), req.name or root.name

    from git import GitError, Repo  # local import: only needed for URL clones

    assert req.url is not None  # guaranteed by AddRepoRequest validator
    target = _clone_dir(state, repo_id)
    try:
        await asyncio.to_thread(Repo.clone_from, req.url, target)
    except GitError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Clone failed: {exc}") from exc
    name = req.name or req.url.rstrip("/").split("/")[-1].removesuffix(".git")
    return str(target), name


async def _run_index(state: AppState, repo_id: str, source: str, name: str) -> None:
    """Background task: run the indexing pipeline, publishing progress to the repo's queue."""
    queue = state.index_queues.setdefault(repo_id, asyncio.Queue())
    loop = asyncio.get_running_loop()

    def on_progress(event: IndexProgress) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, asdict(event))

    try:
        await asyncio.to_thread(state.pipeline.index, source, repo_id, name, on_progress)
        await queue.put({"stage": "done", "message": "Indexing complete"})
    except Exception as exc:  # noqa: BLE001 - surface any failure to the client stream
        logger.exception("Indexing failed for %s", repo_id)
        state.metadata.update_status(repo_id, "error", error=str(exc))
        await queue.put({"stage": "error", "message": str(exc)})


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_repo(
    req: AddRepoRequest, state: AppState = Depends(get_state)
) -> dict[str, Any]:
    """Register a repo and kick off background indexing."""
    repo_id = str(uuid.uuid4())
    source, name = await _resolve_source(state, req, repo_id)
    record = state.metadata.upsert_repo(repo_id, name, source, status="pending")
    state.index_queues[repo_id] = asyncio.Queue()
    asyncio.create_task(_run_index(state, repo_id, source, name))  # noqa: RUF006
    return asdict(record)


@router.get("")
async def list_repos(state: AppState = Depends(get_state)) -> list[dict[str, Any]]:
    return [asdict(r) for r in state.metadata.list_repos()]


@router.get("/{repo_id}")
async def get_repo_details(repo: RepoRecord = Depends(get_repo)) -> dict[str, Any]:
    return asdict(repo)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repo(
    repo: RepoRecord = Depends(get_repo), state: AppState = Depends(get_state)
) -> None:
    state.metadata.delete_repo(repo.id)
    state.index_queues.pop(repo.id, None)
    state.drift_reports.pop(repo.id, None)
    shutil.rmtree(repo_dir(state.data_dir, repo.id), ignore_errors=True)
    shutil.rmtree(_clone_dir(state, repo.id), ignore_errors=True)


@router.get("/{repo_id}/index")
async def index_progress(
    repo: RepoRecord = Depends(get_repo), state: AppState = Depends(get_state)
) -> EventSourceResponse:
    """Stream indexing progress for a repo as SSE events."""
    # If indexing already settled, report the terminal state once instead of blocking.
    if repo.status in {"ready", "error"} and repo.id not in state.index_queues:
        stage = "error" if repo.status == "error" else "done"
        message = repo.error or "Indexing complete"

        async def settled() -> Any:
            yield sse(stage, {"stage": stage, "message": message})

        return EventSourceResponse(settled())

    queue = state.index_queues.setdefault(repo.id, asyncio.Queue())

    async def stream() -> Any:
        while True:
            event = await queue.get()
            stage = event.get("stage", "progress")
            yield sse(stage if stage in _TERMINAL else "progress", event)
            if stage in _TERMINAL:
                break

    return EventSourceResponse(stream())
