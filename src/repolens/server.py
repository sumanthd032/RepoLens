"""FastAPI application factory.

:func:`create_app` assembles the single-process server described in the architecture: the API
routers under ``/api`` plus, when present, the built React frontend served as static files from
``src/repolens/static/`` (populated by ``scripts/build.sh``). Heavy models live on a shared
:class:`~repolens.api.engine.AppState` built once at startup, so requests reuse them.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    else:

        @app.get("/")
        async def root() -> dict[str, Any]:
            return {"name": "RepoLens", "version": __version__, "ui": "not built"}

    return app
