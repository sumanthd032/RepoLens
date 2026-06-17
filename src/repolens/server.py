"""FastAPI application factory.

:func:`create_app` assembles the single-process server described in the architecture: the API
routers under ``/api`` plus, when present, the built React frontend served as static files from
``src/repolens/static/`` (populated by ``scripts/build.sh``). Heavy models live on a shared
:class:`~repolens.api.engine.AppState` built once at startup, so requests reuse them.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from repolens import __version__
from repolens.api import ask, drift, repos
from repolens.api.engine import AppState, build_state
from repolens.config import Config

if TYPE_CHECKING:
    from typing import Any

STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: Config | None = None, state: AppState | None = None) -> FastAPI:
    """Build the RepoLens FastAPI app, optionally with a pre-built :class:`AppState`."""
    state = state or build_state(config)
    app = FastAPI(title="RepoLens", version=__version__)
    app.state.engine = state

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(repos.router)
    app.include_router(ask.router)
    app.include_router(drift.router)

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA: hashed assets plus an index.html fallback for client-side routes."""
    if not STATIC_DIR.is_dir():

        @app.get("/")
        async def root() -> dict[str, Any]:
            return {"name": "RepoLens", "version": __version__, "ui": "not built"}

        return

    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    index_file = STATIC_DIR / "index.html"

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        # API routes are registered first and win; everything else is the single-page app.
        if full_path.startswith("api/"):
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)
