"""Question-answering endpoint: streams grounded answer tokens + citations over SSE."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sse_starlette.sse import EventSourceResponse

from repolens.api.deps import get_repo, get_state
from repolens.api.engine import AppState, answer_events
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from repolens.storage.metadata import RepoRecord

logger = get_logger("api.ask")

router = APIRouter(prefix="/api/repos", tags=["ask"])


class AskRequest(BaseModel):
    query: str

    @field_validator("query")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value


@router.post("/{repo_id}/ask")
async def ask(
    req: AskRequest,
    repo: RepoRecord = Depends(get_repo),
    state: AppState = Depends(get_state),
) -> EventSourceResponse:
    """Answer a question about a repo, streaming token/citation/grounding/done events."""
    if repo.status != "ready":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Repo {repo.id!r} is not ready (status: {repo.status})",
        )
    return EventSourceResponse(answer_events(state, repo, req.query))
