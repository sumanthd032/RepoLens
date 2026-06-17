"""Unit tests for :class:`repolens.ingestion.chunker.SemanticChunker`."""

from __future__ import annotations

from repolens.ingestion.chunker import IndexChunk, SemanticChunker, count_tokens
from repolens.ingestion.parser import ParsedChunk


def _parsed(body: str, start_line: int = 1, symbol: str = "big") -> ParsedChunk:
    return ParsedChunk(
        file_path="big.py",
        symbol_name=symbol,
        symbol_type="function",
        signature="def big()",
        docstring="",
        body=body,
        start_line=start_line,
        end_line=start_line + body.count("\n"),
        language="python",
    )


def _large_function(num_statements: int) -> str:
    """Build a function body with many simple statements (~well over 512 tokens)."""
    lines = ["def big():"]
    for i in range(num_statements):
        lines.append(f"    value_{i} = compute(arg_{i}, other_{i}) + offset_{i}")
    lines.append("    return value_0")
    return "\n".join(lines)


def test_small_chunk_passes_through_unchanged() -> None:
    chunker = SemanticChunker(max_tokens=512, overlap_tokens=64)
    parsed = _parsed("def f():\n    return compute(a, b, c, d)")
    out = chunker.chunk(parsed)
    assert len(out) == 1
    assert out[0].body == parsed.body
    assert out[0].part_total == 1
    assert out[0].token_count == count_tokens(parsed.body)
    assert out[0].chunk_id  # uuid assigned


def test_tiny_chunk_is_dropped() -> None:
    chunker = SemanticChunker(max_tokens=512, overlap_tokens=64, min_tokens=8)
    out = chunker.chunk(_parsed("x = 1"))
    assert out == []


def test_large_function_is_sub_chunked() -> None:
    body = _large_function(120)
    assert count_tokens(body) > 512
    chunker = SemanticChunker(max_tokens=128, overlap_tokens=24)
    out = chunker.chunk(_parsed(body, start_line=10))

    assert len(out) > 1
    # Every sub-chunk respects the max token budget (within a small line-granularity slack).
    for c in out:
        assert c.token_count <= 128 + count_tokens("    value_0 = compute(arg_0, other_0) + offset_0")
    # part metadata is consistent.
    assert [c.part for c in out] == list(range(len(out)))
    assert all(c.part_total == len(out) for c in out)


def test_sub_chunks_have_overlap() -> None:
    body = _large_function(120)
    chunker = SemanticChunker(max_tokens=128, overlap_tokens=24)
    out = chunker.chunk(_parsed(body, start_line=1))

    # Consecutive sub-chunks should share at least one line (overlap), so the next chunk's
    # start line is <= the previous chunk's end line.
    for prev, nxt in zip(out, out[1:], strict=False):
        assert nxt.start_line <= prev.end_line


def test_sub_chunk_line_numbers_are_offset_from_parent() -> None:
    body = _large_function(120)
    chunker = SemanticChunker(max_tokens=128, overlap_tokens=24)
    out = chunker.chunk(_parsed(body, start_line=100))

    assert out[0].start_line == 100
    # Lines stay within the parent's original span.
    parent_end = 100 + body.count("\n")
    assert all(100 <= c.start_line <= c.end_line <= parent_end for c in out)


def test_chunk_all_flattens() -> None:
    chunker = SemanticChunker(max_tokens=512, overlap_tokens=64)
    parsed = [
        _parsed("def a():\n    return compute(a, b, c, d)", symbol="a"),
        _parsed("def b():\n    return compute(e, f, g, h)", symbol="b"),
    ]
    out = chunker.chunk_all(parsed)
    assert len(out) == 2
    assert {c.symbol_name for c in out} == {"a", "b"}


def test_overlap_must_be_smaller_than_max() -> None:
    try:
        SemanticChunker(max_tokens=64, overlap_tokens=64)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_index_chunk_has_unique_ids() -> None:
    body = _large_function(120)
    chunker = SemanticChunker(max_tokens=128, overlap_tokens=24)
    out: list[IndexChunk] = chunker.chunk(_parsed(body))
    ids = [c.chunk_id for c in out]
    assert len(ids) == len(set(ids))
