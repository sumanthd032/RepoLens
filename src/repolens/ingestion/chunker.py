"""Semantic chunker.

:class:`SemanticChunker` converts :class:`~repolens.ingestion.parser.ParsedChunk` objects
into the final :class:`IndexChunk` units that get embedded and indexed. Most parsed symbols
pass through unchanged, but oversized functions/classes are sub-chunked with a sliding window
so each piece fits the embedding model's context. Splits land on safe line boundaries (where
bracket depth is balanced) so a chunk never starts or ends inside a nested block. Chunks below
a minimum token count are dropped as noise.

Token counting is approximate by design: an injected ``token_counter`` keeps the chunker free
of the heavy embedding tokenizer, while still making consistent size decisions. Step 4 can pass
the model's real tokenizer if exact counts are ever needed.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING

from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from repolens.ingestion.parser import ParsedChunk

logger = get_logger("ingestion.chunker")

# Splits code into word, number, and single-punctuation tokens — a stable proxy for the
# subword count without loading a model tokenizer.
_TOKEN_RE = re.compile(r"[A-Za-z_]\w*|\d+|[^\s\w]")
_OPENERS = {"(": ")", "[": "]", "{": "}"}
_CLOSERS = {")", "]", "}"}


def count_tokens(text: str) -> int:
    """Approximate the token count of ``text`` using a code-aware regex tokenizer."""
    return len(_TOKEN_RE.findall(text))


@dataclass
class IndexChunk:
    """A parsed chunk made ready for indexing: identity + token count added."""

    file_path: str
    symbol_name: str
    symbol_type: str
    signature: str
    docstring: str
    body: str
    start_line: int
    end_line: int
    language: str
    token_count: int
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    part: int = 0  # sub-chunk index within the original symbol (0 if not split)
    part_total: int = 1  # number of sub-chunks the original symbol produced


class SemanticChunker:
    """Splits oversized parsed chunks and drops tiny ones.

    Args:
        max_tokens: Soft upper bound on tokens per chunk before sub-splitting.
        overlap_tokens: Tokens of overlap carried between adjacent sub-chunks.
        min_tokens: Chunks below this token count are discarded.
        token_counter: Token-counting function (defaults to :func:`count_tokens`).
    """

    def __init__(
        self,
        max_tokens: int = 512,
        overlap_tokens: int = 64,
        min_tokens: int = 8,
        token_counter: Callable[[str], int] = count_tokens,
    ) -> None:
        if overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be smaller than max_tokens")
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.min_tokens = min_tokens
        self._count = token_counter

    def chunk(self, parsed: ParsedChunk) -> list[IndexChunk]:
        """Convert one :class:`ParsedChunk` into one or more :class:`IndexChunk` objects."""
        total = self._count(parsed.body)
        if total <= self.max_tokens:
            if total < self.min_tokens:
                return []
            return [self._make(parsed, parsed.body, parsed.start_line, parsed.end_line, 0, 1)]
        return self._split(parsed)

    def chunk_all(self, parsed_chunks: list[ParsedChunk]) -> list[IndexChunk]:
        """Chunk a list of parsed chunks, flattening the result."""
        out: list[IndexChunk] = []
        for parsed in parsed_chunks:
            out.extend(self.chunk(parsed))
        return out

    def _split(self, parsed: ParsedChunk) -> list[IndexChunk]:
        """Sliding-window sub-chunking over lines, respecting bracket-balanced boundaries."""
        lines = parsed.body.split("\n")
        line_tokens = [self._count(line) for line in lines]
        safe = self._safe_boundaries(lines)

        windows: list[tuple[int, int]] = []  # (start_line_idx, end_line_idx_exclusive)
        start = 0
        n = len(lines)
        while start < n:
            end = start
            running = 0
            while end < n and (running + line_tokens[end] <= self.max_tokens or end == start):
                running += line_tokens[end]
                end += 1
            # Prefer to end the window on a safe (depth-balanced) boundary.
            if end < n:
                end = self._snap_to_safe(end, start + 1, safe)
            windows.append((start, end))
            if end >= n:
                break
            start = self._overlap_start(end, line_tokens, safe)

        return self._windows_to_chunks(parsed, lines, windows)

    def _windows_to_chunks(
        self, parsed: ParsedChunk, lines: list[str], windows: list[tuple[int, int]]
    ) -> list[IndexChunk]:
        chunks: list[IndexChunk] = []
        kept = [(s, e) for s, e in windows if self._count("\n".join(lines[s:e])) >= self.min_tokens]
        total = len(kept)
        for part, (s, e) in enumerate(kept):
            body = "\n".join(lines[s:e])
            chunks.append(
                self._make(
                    parsed,
                    body,
                    parsed.start_line + s,
                    parsed.start_line + e - 1,
                    part,
                    total,
                )
            )
        return chunks

    def _safe_boundaries(self, lines: list[str]) -> list[bool]:
        """``safe[i]`` is True when a window may start at line ``i`` (bracket depth balanced)."""
        safe = [False] * (len(lines) + 1)
        depth = 0
        safe[0] = True
        for i, line in enumerate(lines):
            for ch in line:
                if ch in _OPENERS:
                    depth += 1
                elif ch in _CLOSERS:
                    depth = max(0, depth - 1)
            safe[i + 1] = depth == 0
        return safe

    @staticmethod
    def _snap_to_safe(end: int, lower: int, safe: list[bool]) -> int:
        """Move ``end`` back to the nearest safe boundary, not before ``lower``."""
        idx = end
        while idx > lower and not safe[idx]:
            idx -= 1
        return idx if safe[idx] else end

    def _overlap_start(self, end: int, line_tokens: list[int], safe: list[bool]) -> int:
        """Back up from ``end`` by ~``overlap_tokens`` worth of lines to a safe boundary."""
        acc = 0
        idx = end
        while idx > 0 and acc < self.overlap_tokens:
            idx -= 1
            acc += line_tokens[idx]
        while idx > 0 and not safe[idx]:
            idx -= 1
        return max(idx, 0) if idx < end else end - 1

    def _make(
        self,
        parsed: ParsedChunk,
        body: str,
        start_line: int,
        end_line: int,
        part: int,
        part_total: int,
    ) -> IndexChunk:
        base = {f.name: getattr(parsed, f.name) for f in fields(parsed)}
        base.update(
            body=body,
            start_line=start_line,
            end_line=end_line,
            token_count=self._count(body),
            part=part,
            part_total=part_total,
        )
        return IndexChunk(**base)
