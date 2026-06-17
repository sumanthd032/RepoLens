"""End-to-end tests for the drift endpoints (Step 8)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from repolens.server import create_app
from tests.e2e.conftest import collect_sse, index_demo, make_state

# The fake LLM returns this verbatim as the claim-extraction response (a JSON array).
_CLAIMS = json.dumps(
    [{"claim": "handle_route returns resolve of the path", "line": 3}]
)


def client_for(app: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def test_drift_post_returns_findings(tmp_path: Path) -> None:
    state = make_state(tmp_path, _CLAIMS)
    repo_id = index_demo(state, tmp_path)
    async with client_for(create_app(state=state)) as client:
        resp = await client.post(f"/api/repos/{repo_id}/drift")

    assert resp.status_code == 200
    report = resp.json()
    assert report["findings"], "expected at least one finding"
    finding = report["findings"][0]
    assert finding["status"] in {"supported", "contradicted", "not_found"}
    # The matching claim should be supported by the handle_route code.
    assert finding["status"] == "supported"
    assert finding["code_file"] == "router.py"
    assert "counts" in report
    assert report["has_contradictions"] is False


async def test_drift_latest_after_run(tmp_path: Path) -> None:
    state = make_state(tmp_path, _CLAIMS)
    repo_id = index_demo(state, tmp_path)
    async with client_for(create_app(state=state)) as client:
        # No report yet.
        missing = await client.get(f"/api/repos/{repo_id}/drift/latest")
        assert missing.status_code == 404
        # Run, then it is available.
        await client.post(f"/api/repos/{repo_id}/drift")
        latest = await client.get(f"/api/repos/{repo_id}/drift/latest")
    assert latest.status_code == 200
    assert latest.json()["findings"]


async def test_drift_stream_emits_progress_and_done(tmp_path: Path) -> None:
    state = make_state(tmp_path, _CLAIMS)
    repo_id = index_demo(state, tmp_path)
    async with client_for(create_app(state=state)) as client:
        events = await collect_sse(client, "GET", f"/api/repos/{repo_id}/drift/stream")

    kinds = [e for e, _ in events]
    assert "progress" in kinds
    assert kinds[-1] == "done"
    report = events[-1][1]
    assert report["findings"]


async def test_drift_unknown_repo_404(tmp_path: Path) -> None:
    state = make_state(tmp_path, _CLAIMS)
    async with client_for(create_app(state=state)) as client:
        resp = await client.post("/api/repos/nope/drift")
    assert resp.status_code == 404
