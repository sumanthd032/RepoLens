"""Drift-detection endpoints: run a check, fetch the latest report, stream progress."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from repolens.api.deps import get_repo, get_state
from repolens.api.engine import AppState, drift_events, friendly_llm_error, run_drift
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from repolens.storage.metadata import RepoRecord

logger = get_logger("api.drift")

router = APIRouter(prefix="/api/repos", tags=["drift"])


def _require_ready(repo: RepoRecord) -> None:
    if repo.status != "ready":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Repo {repo.id!r} is not ready (status: {repo.status})",
        )


@router.post("/{repo_id}/drift")
async def run_drift_check(
    repo: RepoRecord = Depends(get_repo), state: AppState = Depends(get_state)
) -> dict[str, Any]:
    """Run drift detection and return the report (also cached as the latest report)."""
    _require_ready(repo)
    try:
        reporter = await run_drift(state, repo)
    except Exception as exc:
        message, _etype = friendly_llm_error(exc)
        logger.warning("Drift check failed for %s: %s", repo.id, exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, message) from exc
    return reporter.to_json()


@router.get("/{repo_id}/drift/latest")
async def latest_drift(
    repo: RepoRecord = Depends(get_repo), state: AppState = Depends(get_state)
) -> dict[str, Any]:
    """Return the most recent drift report for a repo."""
    report = state.drift_reports.get(repo.id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No drift report yet; run a check first")
    return report


@router.get("/{repo_id}/drift/stream")
async def drift_stream(
    repo: RepoRecord = Depends(get_repo), state: AppState = Depends(get_state)
) -> EventSourceResponse:
    """Run drift detection, streaming progress events and a final report."""
    _require_ready(repo)
    return EventSourceResponse(drift_events(state, repo))
