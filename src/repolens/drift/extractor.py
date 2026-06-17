"""Documentation claim extraction.

Drift detection compares what the docs *say* against what the code *does*. The first step is
turning prose into discrete, checkable assertions: :class:`ClaimExtractor` asks the LLM to pull
factual, verifiable claims about behaviour ("the default timeout is 30s", "returns nil on error")
out of each documentation file, each tagged with its source location. :func:`iter_doc_files`
collects the documentation to scan, applying the same ignore rules as code indexing.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from repolens.utils.ignore import IgnoreFilter
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from repolens.generation.llm.base import BaseLLMClient

logger = get_logger("drift.extractor")

DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".txt"}

_SYSTEM = (
    "You extract factual, verifiable claims about software behaviour from documentation. A claim "
    "is a single statement that could be checked against source code (defaults, return values, "
    "error handling, supported options, limits). Ignore marketing, install steps, and examples. "
    'Respond ONLY with a JSON array of objects {"claim": str, "line": int}, where line is the '
    "1-based line number in the document where the claim appears. Return [] if there are none."
)
_USER = "Document: {name}\n\n{numbered}\n\nExtract the verifiable claims as a JSON array:"


@dataclass(frozen=True)
class DocClaim:
    """A single factual claim extracted from documentation."""

    claim: str
    doc_file: str
    doc_line: int


def iter_doc_files(
    repo_path: str | Path, ignore_filter: IgnoreFilter | None = None
) -> Iterator[tuple[str, str]]:
    """Yield ``(relative_path, text)`` for each documentation file under ``repo_path``."""
    root = Path(repo_path).expanduser().resolve()
    ignore = ignore_filter or IgnoreFilter.for_repo(root)
    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError:  # pragma: no cover - permission/race edge case
            continue
        for entry in entries:
            rel = entry.relative_to(root).as_posix()
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if not ignore.is_ignored(rel + "/"):
                    stack.append(entry)
            elif entry.is_file() and entry.suffix.lower() in DOC_EXTENSIONS:
                if not ignore.is_ignored(rel):
                    yield rel, entry.read_text(encoding="utf-8", errors="replace")


def _number_lines(text: str) -> str:
    return "\n".join(f"{i}: {line}" for i, line in enumerate(text.splitlines(), start=1))


def _parse_claims(raw: str) -> list[dict[str, object]]:
    """Pull the first JSON array out of an LLM response, tolerating surrounding prose/fences."""
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("Could not parse claim JSON from LLM response")
        return []
    return [item for item in data if isinstance(item, dict) and "claim" in item]


class ClaimExtractor:
    """Extracts :class:`DocClaim` objects from documentation using an LLM."""

    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm = llm_client

    async def extract(self, doc_file: str, text: str) -> list[DocClaim]:
        """Extract claims from one document's ``text``."""
        if not text.strip():
            return []
        user = _USER.format(name=doc_file, numbered=_number_lines(text))
        raw = await self.llm.complete([{"role": "user", "content": user}], _SYSTEM)
        claims: list[DocClaim] = []
        line_count = len(text.splitlines())
        for item in _parse_claims(raw):
            claim_text = str(item["claim"]).strip()
            if not claim_text:
                continue
            line = item.get("line", 1)
            doc_line = int(line) if isinstance(line, int) else 1
            doc_line = max(1, min(doc_line, line_count or 1))
            claims.append(DocClaim(claim=claim_text, doc_file=doc_file, doc_line=doc_line))
        return claims

    async def extract_repo(
        self, repo_path: str | Path, ignore_filter: IgnoreFilter | None = None
    ) -> list[DocClaim]:
        """Extract claims from every documentation file in the repository."""
        claims: list[DocClaim] = []
        for rel_path, text in iter_doc_files(repo_path, ignore_filter):
            claims.extend(await self.extract(rel_path, text))
        logger.info("Extracted %d claims from documentation", len(claims))
        return claims
