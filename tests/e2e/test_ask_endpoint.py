"""End-to-end tests for the repos + ask endpoints (Step 8)."""

from __future__ import annotations

from pathlib import Path

import httpx

from repolens.server import create_app
from tests.e2e.conftest import collect_sse, index_demo, make_state

_GROUNDED = "The handle_route function dispatches to resolve [router.py:1-2]."
_BAD_CITATION = "Routing happens somewhere [router.py:999]."


def client_for(app: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def test_list_repos_empty(tmp_path: Path) -> None:
    state = make_state(tmp_path, _GROUNDED)
    async with client_for(create_app(state=state)) as client:
        resp = await client.get("/api/repos")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_indexed_repo_listed_and_ready(tmp_path: Path) -> None:
    state = make_state(tmp_path, _GROUNDED)
    repo_id = index_demo(state, tmp_path)
    async with client_for(create_app(state=state)) as client:
        resp = await client.get(f"/api/repos/{repo_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["num_files"] == 1
    assert body["languages"] == ["python"]


async def test_ask_streams_grounded_answer(tmp_path: Path) -> None:
    state = make_state(tmp_path, _GROUNDED)
    repo_id = index_demo(state, tmp_path)
    async with client_for(create_app(state=state)) as client:
        events = await collect_sse(
            client, "POST", f"/api/repos/{repo_id}/ask", json={"query": "how does routing work"}
        )

    kinds = [e for e, _ in events]
    assert "token" in kinds
    assert "citation" in kinds
    assert "grounding" in kinds
    assert kinds[-1] == "done"

    # The streamed tokens reconstruct the answer.
    text = "".join(d["text"] for e, d in events if e == "token")
    assert "handle_route" in text

    # The citation resolves to the real file/symbol.
    citation = next(d for e, d in events if e == "citation")
    assert citation["file"] == "router.py"
    assert citation["start"] == 1
    assert citation["symbol"] == "handle_route"

    grounding = next(d for e, d in events if e == "grounding")
    assert 0.0 <= grounding["score"] <= 1.0
    assert grounding["verdict"] in {"high", "medium", "low", "none"}


async def test_ask_bad_citation_is_rejected(tmp_path: Path) -> None:
    # The model only ever returns a citation to a non-existent line; after retries the answer
    # must be rejected, not streamed (Invariant 2).
    state = make_state(tmp_path, _BAD_CITATION)
    repo_id = index_demo(state, tmp_path)
    async with client_for(create_app(state=state)) as client:
        events = await collect_sse(
            client, "POST", f"/api/repos/{repo_id}/ask", json={"query": "routing"}
        )

    kinds = [e for e, _ in events]
    assert "token" not in kinds
    error = next(d for e, d in events if e == "error")
    assert error["type"] == "validation_failed"


async def test_ask_unknown_repo_404(tmp_path: Path) -> None:
    state = make_state(tmp_path, _GROUNDED)
    async with client_for(create_app(state=state)) as client:
        resp = await client.post("/api/repos/nope/ask", json={"query": "x"})
    assert resp.status_code == 404


async def test_ask_empty_query_422(tmp_path: Path) -> None:
    state = make_state(tmp_path, _GROUNDED)
    repo_id = index_demo(state, tmp_path)
    async with client_for(create_app(state=state)) as client:
        resp = await client.post(f"/api/repos/{repo_id}/ask", json={"query": "   "})
    assert resp.status_code == 422
