"""Self-index smoke test (used by .github/workflows/self-index.yml).

Indexes the RepoLens repository itself, asks a known question, and asserts the answer's grounding
score clears a threshold — a nightly end-to-end check that ingestion, retrieval, generation, and
grounding still work together. Exits non-zero if grounding is too low or no answer is produced.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from repolens.api.engine import answer_events, build_state

QUESTION = "What does the citation validator do?"
MIN_GROUNDING = 0.6


async def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    state = build_state()

    print(f"Indexing {repo_root} ...")
    result = state.pipeline.index(repo_root, name="repolens")
    print(f"Indexed {result.num_files} files, {result.num_chunks} chunks.")

    repo = state.metadata.get_repo(result.repo_id)
    assert repo is not None

    grounding: float | None = None
    answer = ""
    async for event in answer_events(state, repo, QUESTION):
        if event["event"] == "token":
            answer += "."
        elif event["event"] == "grounding":
            import json

            grounding = json.loads(event["data"])["score"]
        elif event["event"] == "error":
            print(f"Answer error: {event['data']}", file=sys.stderr)
            return 1

    if grounding is None:
        print("No grounding score was produced.", file=sys.stderr)
        return 1

    print(f"Grounding score: {grounding:.2f} (threshold {MIN_GROUNDING})")
    if grounding < MIN_GROUNDING:
        print("Grounding below threshold — failing.", file=sys.stderr)
        return 1
    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
