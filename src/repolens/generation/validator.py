"""Citation validation.

The model is instructed to cite ``[path:start-end]`` spans, but instructions are not a guarantee.
:class:`CitationValidator` enforces Invariant 2: every cited span is re-opened on disk and checked
to (a) point at a file that exists and (b) cover a line range that exists in that file. A citation
that fails either check invalidates the answer, which the generation loop then regenerates. For
surviving citations a cheap lexical similarity to the sentence that cited them is computed, so weak
(technically-valid but irrelevant) citations can be surfaced without blocking the answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from repolens.utils.logger import get_logger

logger = get_logger("generation.validator")

# Matches a citation span like [src/pkg/router.py:42-67] or [main.go:10] (single line).
CITATION_RE = re.compile(r"\[([^\[\]\s:]+):(\d+)(?:-(\d+))?\]")
# Splits answer text into sentences on terminal punctuation (kept simple on purpose).
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?")
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class Citation:
    """A ``[file:start-end]`` span referenced in an answer."""

    file: str
    start: int
    end: int
    symbol: str | None = None


@dataclass
class CitationCheck:
    """The outcome of validating one citation."""

    citation: Citation
    exists: bool
    similarity: float
    reason: str = ""


@dataclass
class ValidationResult:
    """Aggregate validation outcome for an answer."""

    ok: bool
    checks: list[CitationCheck] = field(default_factory=list)
    invalid_citations: list[Citation] = field(default_factory=list)
    reason: str = ""


def parse_citations(answer_text: str) -> list[Citation]:
    """Extract unique citations from ``answer_text`` in first-seen order."""
    seen: set[tuple[str, int, int]] = set()
    citations: list[Citation] = []
    for match in CITATION_RE.finditer(answer_text):
        file = match.group(1)
        start = int(match.group(2))
        end = int(match.group(3)) if match.group(3) else start
        key = (file, start, end)
        if key not in seen:
            seen.add(key)
            citations.append(Citation(file=file, start=start, end=end))
    return citations


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class CitationValidator:
    """Validates that an answer's citations point at real, in-range file spans."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path)

    def validate(
        self, answer_text: str, citations: list[Citation] | None = None
    ) -> ValidationResult:
        """Validate ``citations`` (parsed from ``answer_text`` if not supplied)."""
        if citations is None:
            citations = parse_citations(answer_text)

        if not citations:
            return ValidationResult(
                ok=False, reason="Answer contains no citations; every sentence must cite a span."
            )

        sentence_for = self._sentence_index(answer_text)
        checks: list[CitationCheck] = []
        invalid: list[Citation] = []

        for citation in citations:
            lines = self._read_lines(citation.file)
            if lines is None:
                checks.append(
                    CitationCheck(citation, exists=False, similarity=0.0, reason="file not found")
                )
                invalid.append(citation)
                continue
            if not self._range_ok(citation, len(lines)):
                checks.append(
                    CitationCheck(
                        citation,
                        exists=False,
                        similarity=0.0,
                        reason=f"line range {citation.start}-{citation.end} outside "
                        f"file of {len(lines)} lines",
                    )
                )
                invalid.append(citation)
                continue

            snippet = "\n".join(lines[citation.start - 1 : citation.end])
            sentence = sentence_for.get((citation.file, citation.start, citation.end), answer_text)
            similarity = _jaccard(_tokens(snippet), _tokens(sentence))
            checks.append(CitationCheck(citation, exists=True, similarity=similarity))

        ok = not invalid
        reason = "" if ok else f"{len(invalid)} citation(s) point to non-existent spans"
        return ValidationResult(ok=ok, checks=checks, invalid_citations=invalid, reason=reason)

    @staticmethod
    def _range_ok(citation: Citation, num_lines: int) -> bool:
        return 1 <= citation.start <= citation.end <= num_lines

    def _read_lines(self, rel_path: str) -> list[str] | None:
        path = self.repo_path / rel_path
        try:
            return path.read_text(encoding="utf-8", errors="replace").splitlines()
        except (FileNotFoundError, IsADirectoryError, OSError):
            return None

    @staticmethod
    def _sentence_index(answer_text: str) -> dict[tuple[str, int, int], str]:
        """Map each citation key to the sentence it appears in, for similarity scoring."""
        index: dict[tuple[str, int, int], str] = {}
        for sentence in _SENTENCE_RE.findall(answer_text):
            for citation in parse_citations(sentence):
                index[(citation.file, citation.start, citation.end)] = sentence.strip()
        return index
